import hashlib
from io import BytesIO

import yaml
from cerberus import Validator
from flask import Blueprint, request, send_file
from werkzeug.exceptions import BadRequest, NotFound

from psma.common.utils import verify_sha256_hash
from psma.extensions import db, sftp_controller
from psma.models.module import Module, ModuleVersion, create_module_yaml, create_module_version_yaml, \
    module_schema, create_module

blueprint = Blueprint('module', __name__, url_prefix=f'/{"/".join(__name__.split(".")[-2:])}')


@blueprint.route('/', methods=['GET'])
def get_all_modules():
    modules = {
        'modules': [create_module_yaml(module, ModuleVersion.query.filter_by(id=module.id))
                    for module in Module.query.all()]
    }

    modules_file = BytesIO(yaml.dump(modules).encode())

    return send_file(modules_file,
                     mimetype='application/x-yaml',
                     as_attachment=True,
                     attachment_filename=f'modules.yaml')


@blueprint.route('/', methods=['POST'])
def upload_module():
    try:
        definition_file = request.files.get('module_definition')
        module_file = request.files.get('module')
    except ValueError as ve:
        raise BadRequest(ve.__str__())

    module_hash = hashlib.sha256(module_file.read()).digest().hex()
    module, module_version = parse_definition(definition_file, module_hash)

    db.session.add(module)
    db.session.add(module_version)

    sftp_controller.folder_create(f'module/{module.id}')
    sftp_controller.file_create(module_file, f'module/{module.id}/{module_hash}')
    db.session.commit()

    module_file = BytesIO(yaml.dump(create_module_yaml(module, [module_version])).encode())

    return send_file(module_file,
                     mimetype='application/x-yaml',
                     as_attachment=True,
                     attachment_filename=f'module_{module.id}_def.yaml')


@blueprint.route('/<uuid:module_id>', methods=['GET'])
def get_module_info(module_id):
    module = Module.query.filter_by(id=module_id).first()
    if module is None:
        raise NotFound(description=f'Not found error: No Module with id {module_id} was found.')

    module_yaml = create_module_yaml(module, ModuleVersion.query.filter_by(id=module.id))
    module_file = BytesIO(yaml.dump(module_yaml).encode())

    return send_file(module_file,
                     mimetype='application/x-yaml',
                     as_attachment=True,
                     attachment_filename=f'module_{module.id}_def.yaml')


@blueprint.route('/<uuid:module_id>', methods=['PUT'])
def update_module(module_id):
    try:
        comment = request.form.get('comment', '')
        module_version_file = request.files.get('module')
    except ValueError as ve:
        raise BadRequest(ve.__str__())

    if Module.query.filter_by(id=module_id).first() is None:
        raise NotFound(description=f'Not found error: No Module with id {module_id} was found.')

    module_hash = hashlib.sha256(module_version_file.read()).digest().hex()

    if ModuleVersion.query.filter_by(id=module_id, hash=module_hash).first() is not None:
        raise BadRequest(description=f'Duplicated error: Module Version with  id {module_id} and hash {module_hash} is '
                                     f'already in the system.')

    module_version = ModuleVersion(
        id=module_id,
        hash=module_hash,
        comment=comment
    )

    db.session.add(module_version)

    sftp_controller.file_create(module_version_file, f'module/{module_id}/{module_hash}')
    db.session.commit()

    module_version_yaml = create_module_version_yaml(Module.query.filter_by(id=module_id).first(), module_version)
    module_version_file = BytesIO(yaml.dump(module_version_yaml).encode())

    return send_file(module_version_file,
                     mimetype='application/x-yaml',
                     as_attachment=True,
                     attachment_filename=f'module_{module_version.id}_{module_version.hash}_def.yaml')


@blueprint.route('/<uuid:module_id>', methods=['DELETE'])
def delete_module(module_id):
    module = Module.query.filter_by(id=module_id).first()

    if module is None:
        raise NotFound(description=f'Not found error: No Module with id {module_id} was found.')

    for module_version in ModuleVersion.query.filter_by(id=module.id):
        db.delete(module_version)
    db.session.delete(module)
    sftp_controller.folder_delete(f'module/{module_id}')

    db.session.commit()
    return '', 204


@blueprint.route('/<uuid:module_id>/download', methods=['GET'])
def download_latest_module(module_id):
    if Module.query.filter_by(id=module_id).first() is None:
        raise NotFound(description=f'Not found error: No Module with id {module_id} was found.')

    latest_module = ModuleVersion.query.filter_by(id=module_id).order_by(ModuleVersion.timestamp.desc()).first()

    if latest_module is None:
        raise NotFound(description=f'Not found error: No Module version with id {module_id} was found.')

    module_file = sftp_controller.file_read(f'module/{latest_module.id}/{latest_module.hash}')
    return send_file(module_file,
                     mimetype='application/octet-stream',
                     as_attachment=True,
                     attachment_filename=f'module_{latest_module.id}_{latest_module.hash}.ova')


@blueprint.route('/<uuid:module_id>/<module_hash>', methods=['GET'])
def get_module_version_info(module_id, module_hash):
    if not verify_sha256_hash(module_hash):
        raise BadRequest(description=f'Malformed hash: Hash {module_hash} is not a valid SHA256 hash')

    module_version = ModuleVersion.query.filter_by(id=module_id, hash=module_hash).first()

    if module_version is None:
        raise NotFound(
            description=f'Not found error: No Module version with id {module_id} and hash {module_hash} was found.')

    module_version_yaml = create_module_version_yaml(Module.query.filter_by(id=module_id), module_version)
    module_version_file = BytesIO(yaml.dump(module_version_yaml).encode())

    return send_file(module_version_file,
                     mimetype='application/x-yaml',
                     as_attachment=True,
                     attachment_filename=f'module_{module_version.id}_{module_version.hash}_def.yaml')


@blueprint.route('/<uuid:module_id>/<module_hash>', methods=['DELETE'])
def delete_module_version(module_id, module_hash):
    if not verify_sha256_hash(module_hash):
        raise BadRequest(description=f'Malformed hash: Hash {module_hash} is not a valid SHA256 hash')

    module_version = ModuleVersion.query.filter_by(id=module_id, hash=module_hash).first()

    if module_version is None:
        raise NotFound(
            description=f'Not found error: No Module version with id {module_id} and hash {module_hash} was found.')

    sftp_controller.file_delete(f'module/{module_id}/{module_version.hash}')
    db.session.delete(module_version)

    db.session.commit()
    return '', 204


@blueprint.route('/<uuid:module_id>/<module_hash>/download', methods=['GET'])
def download_specific_module_version(module_id, module_hash):
    if not verify_sha256_hash(module_hash):
        raise BadRequest(description=f'Malformed hash: Hash {module_hash} is not a valid SHA256 hash')

    module_version = ModuleVersion.query.filter_by(id=module_id, hash=module_hash).first()

    if module_version is None:
        raise NotFound(
            description=f'Not found error: No Module version with id {module_id} and hash {module_hash} was found.')

    module_file = sftp_controller.file_read(f'module/{module_version.id}/{module_version.hash.hex()}')
    return send_file(module_file,
                     mimetype='application/octet-stream',
                     as_attachment=True,
                     attachment_filename=f'module_{module_version.id}_{module_version.hash}.ova')


def parse_definition(definition_file, module_hash: str):
    validator = Validator(module_schema)

    try:
        definition = yaml.safe_load(definition_file)
        normalized_definition = validator.normalized(definition)

        if validator.errors:
            raise Exception(validator.errors)

    except Exception as e:
        raise BadRequest(e.__str__())

    return create_module(normalized_definition, module_hash)
