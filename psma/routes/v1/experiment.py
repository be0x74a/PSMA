import hashlib
from io import BytesIO
from zipfile import ZipFile

import yaml
from cerberus import Validator
from flask import Blueprint, request, send_file
from werkzeug.exceptions import BadRequest, NotFound

from psma.extensions import db, sftp_controller
from psma.models.experiment import Experiment, ExperimentSample, experiment_schema, create_experiment, \
    create_experiment_yaml, ExperimentStatus
from psma.models.module import ModuleVersion
from psma.models.vmi import VMIVersion
from psma.workers.tasks import launch_experiment

blueprint = Blueprint('experiment', __name__, url_prefix=f'/{"/".join(__name__.split(".")[-2:])}')


@blueprint.route('/', methods=['GET'])
def get_all_experiments():
    experiments = {
        'experiments': [create_experiment_yaml(experiment, ExperimentSample.query.filter_by(id=experiment.id))
                        for experiment in Experiment.query.all()]
    }

    experiments_file = BytesIO(yaml.dump(experiments).encode())

    return send_file(experiments_file,
                     mimetype='application/x-yaml',
                     as_attachment=True,
                     attachment_filename=f'experiments.yaml')


@blueprint.route('/', methods=['POST'])
def upload_experiment_file():
    try:
        definition_file = request.files.get('experiment')
        samples_zip = request.files.get('samples')
    except ValueError as ve:
        raise BadRequest(ve.__str__())

    experiment = parse_definition(definition_file)
    samples = parse_samples(experiment, samples_zip)

    db.session.add(experiment)
    db.session.add_all(samples)
    db.session.commit()

    launch_experiment(experiment, samples)

    experiment_file = BytesIO(yaml.dump(create_experiment_yaml(experiment, samples)).encode())

    return send_file(experiment_file,
                     mimetype='application/x-yaml',
                     as_attachment=True,
                     attachment_filename=f'exp_{experiment.id}_def.yaml')


@blueprint.route('/<uuid:experiment_id>', methods=['GET'])
def get_experiment_info(experiment_id):
    experiment = Experiment.query.filter_by(id=experiment_id).first()
    if experiment is None:
        raise NotFound(description=f'Not found error: No experiment with id {experiment_id} was found.')

    experiment_yaml = create_experiment_yaml(experiment, ExperimentSample.query.filter_by(id=experiment.id))
    experiment_file = BytesIO(yaml.dump(experiment_yaml).encode())

    return send_file(experiment_file,
                     mimetype='application/x-yaml',
                     as_attachment=True,
                     attachment_filename=f'exp_{experiment.id}_def.yaml')


@blueprint.route('/<uuid:experiment_id>/status', methods=['GET'])
def get_experiment_status(experiment_id):
    experiment = Experiment.query.filter_by(id=experiment_id).first()
    if experiment is None:
        raise NotFound(description=f'Not found error: No experiment with id {experiment_id} was found.')

    status = {
        'experiment': {
            'id': str(experiment.id),
            'overall_status': experiment.status.name,
            'samples_status': [{
                'hash': sample.hash,
                'status': sample.status.name
            } for sample in ExperimentSample.query.filter_by(id=experiment.id)]
        }
    }

    status_file = BytesIO(yaml.dump(status).encode())

    return send_file(status_file,
                     mimetype='application/x-yaml',
                     as_attachment=True,
                     attachment_filename=f'exp_{experiment.id}_status.yaml')


@blueprint.route('/<uuid:experiment_id>/result', methods=['GET'])
def download_specific_module_version(experiment_id):
    experiment = Experiment.query.filter_by(id=experiment_id).first()
    if experiment is None:
        raise NotFound(description=f'Not found error: No experiment with id {experiment_id} was found.')

    if experiment.status != ExperimentStatus.FINISHED:
        raise BadRequest(description=f'Experiment with id {experiment.id} is still in {experiment.status} status')

    results_file = sftp_controller.file_read(f'experiment/{experiment_id}/result.zip')

    return send_file(results_file,
                     mimetype='application/zip',
                     as_attachment=True,
                     attachment_filename=f'exp_{experiment.id}_result.zip')


@blueprint.route('/<uuid:experiment_id>', methods=['DELETE'])
def delete_experiment(experiment_id):
    experiment = Experiment.query.filter_by(id=experiment_id).first()

    if experiment is None:
        raise NotFound(description=f'Not found error: No experiment with id {experiment_id} was found.')

    if sftp_controller.folder_exists(f'experiment/{experiment_id}'):
        sftp_controller.folder_delete(f'experiment/{experiment_id}')

    for sample in ExperimentSample.query.filter_by(id=experiment.id):
        db.delete(sample)
    db.session.delete(experiment)
    db.session.commit()

    return '', 204


def parse_definition(definition_file):
    validator = Validator(experiment_schema)

    try:
        definition = yaml.safe_load(definition_file)
        normalized_definition = validator.normalized(definition)

        if validator.errors:
            raise Exception(validator.errors)

        if not normalized_definition['experiment']['vmi']['hash']:
            normalized_definition['experiment']['vmi']['hash'] = VMIVersion \
                .query.filter_by(id=normalized_definition['experiment']['vmi']['id']) \
                .order_by(VMIVersion.timestamp.desc()) \
                .first().hash

        if not normalized_definition['experiment']['dcs_module']['hash']:
            normalized_definition['experiment']['dcs_module']['hash'] = ModuleVersion \
                .query.filter_by(id=normalized_definition['experiment']['dcs_module']['id']) \
                .order_by(ModuleVersion.timestamp.desc()) \
                .first().hash

        if not normalized_definition['experiment']['dps_module']['hash']:
            normalized_definition['experiment']['dps_module']['hash'] = ModuleVersion \
                .query.filter_by(id=normalized_definition['experiment']['dps_module']['id']) \
                .order_by(ModuleVersion.timestamp.desc()) \
                .first().hash

    except Exception as e:
        raise BadRequest(e.__str__())

    return create_experiment(normalized_definition)


def parse_samples(experiment: Experiment, samples_zip):
    samples = []
    zf = ZipFile(samples_zip)

    sftp_controller.folder_create(f'experiment/{experiment.id}')
    sftp_controller.folder_create(f'experiment/{experiment.id}/samples')
    sftp_controller.folder_create(f'experiment/{experiment.id}/collected')

    for member in zf.infolist():
        if not member.is_dir():
            sample_file = zf.read(member)
            sample_hash = hashlib.sha256(sample_file).digest().hex()
            sample = ExperimentSample(
                id=experiment.id,
                hash=sample_hash,
                original_name=member.filename
            )

            sftp_controller.file_create(BytesIO(sample_file),
                                        f'experiment/{experiment.id}/samples/{sample_hash}')
            samples.append(sample)

    return samples
