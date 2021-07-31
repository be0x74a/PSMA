import hashlib
from io import BytesIO

import yaml
from cerberus import Validator
from flask import Blueprint, request, send_file
from werkzeug.exceptions import BadRequest, NotFound

from psma.common.utils import verify_sha256_hash
from psma.extensions import db, sftp_controller
from psma.models.vmi import VMI, VMIVersion, create_vmi_yaml, vmi_schema, create_vmi, create_vmi_version_yaml

blueprint = Blueprint('vmi', __name__, url_prefix=f'/{"/".join(__name__.split(".")[-2:])}')


@blueprint.route('/', methods=['GET'])
def get_all_vmis():
    vmis = {
        'vmis': [create_vmi_yaml(vmi, VMIVersion.query.filter_by(id=vmi.id))
                 for vmi in VMI.query.all()]
    }

    vmis_file = BytesIO(yaml.dump(vmis).encode())

    return send_file(vmis_file,
                     mimetype='application/x-yaml',
                     as_attachment=True,
                     attachment_filename=f'vmis.yaml')


@blueprint.route('/', methods=['POST'])
def upload_vmi():
    try:
        definition_file = request.files.get('vmi_definition')
        vmi_file = request.files.get('vmi')
    except ValueError as ve:
        raise BadRequest(ve.__str__())

    vmi_hash = hashlib.sha256(vmi_file.read()).digest().hex()
    vmi, vmi_version = parse_definition(definition_file, vmi_hash)

    db.session.add(vmi)
    db.session.add(vmi_version)

    sftp_controller.folder_create(f'vmi/{vmi.id}')
    sftp_controller.file_create(vmi_file, f'vmi/{vmi.id}/{vmi_hash}')
    db.session.commit()

    vmi_file = BytesIO(yaml.dump(create_vmi_yaml(vmi, [vmi_version])).encode())

    return send_file(vmi_file,
                     mimetype='application/x-yaml',
                     as_attachment=True,
                     attachment_filename=f'vmi_{vmi.id}_def.yaml')


@blueprint.route('/<uuid:vmi_id>', methods=['GET'])
def get_vmi_info(vmi_id):
    vmi = VMI.query.filter_by(id=vmi_id).first()
    if vmi is None:
        raise NotFound(description=f'Not found error: No VMI with id {vmi_id} was found.')

    vmi_yaml = create_vmi_yaml(vmi, VMIVersion.query.filter_by(id=vmi.id))
    vmi_file = BytesIO(yaml.dump(vmi_yaml).encode())

    return send_file(vmi_file,
                     mimetype='application/x-yaml',
                     as_attachment=True,
                     attachment_filename=f'vmi_{vmi.id}_def.yaml')


@blueprint.route('/<uuid:vmi_id>', methods=['PUT'])
def update_vmi(vmi_id):
    try:
        comment = request.form.get('comment', '')
        vmi_version_file = request.files.get('vmi')
    except ValueError as ve:
        raise BadRequest(ve.__str__())

    if VMI.query.filter_by(id=vmi_id).first() is None:
        raise NotFound(description=f'Not found error: No VMI with id {vmi_id} was found.')

    vmi_hash = hashlib.sha256(vmi_version_file.read()).digest().hex()

    if VMIVersion.query.filter_by(id=vmi_id, hash=vmi_hash).first() is not None:
        raise BadRequest(description=f'Duplicated error: VMI Version with  id {vmi_id} and hash {vmi_hash} is already '
                                     f'in the system.')

    vmi_version = VMIVersion(
        id=vmi_id,
        hash=vmi_hash,
        comment=comment
    )

    db.session.add(vmi_version)

    sftp_controller.file_create(vmi_version_file, f'vmi/{vmi_id}/{vmi_hash}')
    db.session.commit()

    vmi_version_yaml = create_vmi_version_yaml(VMI.query.filter_by(id=vmi_id).first(), vmi_version)
    vmi_version_file = BytesIO(yaml.dump(vmi_version_yaml).encode())

    return send_file(vmi_version_file,
                     mimetype='application/x-yaml',
                     as_attachment=True,
                     attachment_filename=f'vmi_{vmi_version.id}_{vmi_version.hash}_def.yaml')


@blueprint.route('/<uuid:vmi_id>', methods=['DELETE'])
def delete_vmi(vmi_id):
    vmi = VMI.query.filter_by(id=vmi_id).first()

    if vmi is None:
        raise NotFound(description=f'Not found error: No VMI with id {vmi_id} was found.')

    for vmi_version in VMIVersion.query.filter_by(id=vmi.id):
        db.delete(vmi_version)
    db.session.delete(vmi)
    sftp_controller.folder_delete(f'vmi/{vmi_id}')

    db.session.commit()
    return '', 204


@blueprint.route('/<uuid:vmi_id>/download', methods=['GET'])
def download_latest_vmi(vmi_id):
    if VMI.query.filter_by(id=vmi_id).first() is None:
        raise NotFound(description=f'Not found error: No VMI with id {vmi_id} was found.')

    latest_vmi = VMIVersion.query.filter_by(id=vmi_id).order_by(VMIVersion.timestamp.desc()).first()

    if latest_vmi is None:
        raise NotFound(description=f'Not found error: No VMI version with id {vmi_id} was found.')

    vmi_file = sftp_controller.file_read(f'vmi/{latest_vmi.id}/{latest_vmi.hash}')
    return send_file(vmi_file,
                     mimetype='application/octet-stream',
                     as_attachment=True,
                     attachment_filename=f'vmi_{latest_vmi.id}_{latest_vmi.hash}.ova')


@blueprint.route('/<uuid:vmi_id>/<vmi_hash>', methods=['GET'])
def get_vmi_version_info(vmi_id, vmi_hash):
    if not verify_sha256_hash(vmi_hash):
        raise BadRequest(description=f'Malformed hash: Hash {vmi_hash} is not a valid SHA256 hash')

    vmi_version = VMIVersion.query.filter_by(id=vmi_id, hash=vmi_hash).first()

    if vmi_version is None:
        raise NotFound(description=f'Not found error: No VMI version with id {vmi_id} and hash {vmi_hash} was found.')

    vmi_version_yaml = create_vmi_version_yaml(VMI.query.filter_by(id=vmi_id), vmi_version)
    vmi_version_file = BytesIO(yaml.dump(vmi_version_yaml).encode())

    return send_file(vmi_version_file,
                     mimetype='application/x-yaml',
                     as_attachment=True,
                     attachment_filename=f'vmi_{vmi_version.id}_{vmi_version.hash}_def.yaml')


@blueprint.route('/<uuid:vmi_id>/<vmi_hash>', methods=['DELETE'])
def delete_vmi_version(vmi_id, vmi_hash):
    if not verify_sha256_hash(vmi_hash):
        raise BadRequest(description=f'Malformed hash: Hash {vmi_hash} is not a valid SHA256 hash')

    vmi_version = VMIVersion.query.filter_by(id=vmi_id, hash=vmi_hash).first()

    if vmi_version is None:
        raise NotFound(description=f'Not found error: No VMI version with id {vmi_id} and hash {vmi_hash} was found.')

    sftp_controller.file_delete(f'vmi/{vmi_id}/{vmi_version.hash}')
    db.session.delete(vmi_version)

    db.session.commit()
    return '', 204


@blueprint.route('/<uuid:vmi_id>/<vmi_hash>/download', methods=['GET'])
def download_specific_vmi_version(vmi_id, vmi_hash):
    if not verify_sha256_hash(vmi_hash):
        raise BadRequest(description=f'Malformed hash: Hash {vmi_hash} is not a valid SHA256 hash')

    vmi_version = VMIVersion.query.filter_by(id=vmi_id, hash=vmi_hash).first()

    if vmi_version is None:
        raise NotFound(description=f'Not found error: No VMI version with id {vmi_id} and hash {vmi_hash} was found.')

    vmi_file = sftp_controller.file_read(f'vmi/{vmi_version.id}/{vmi_version.hash.hex()}')
    return send_file(vmi_file,
                     mimetype='application/octet-stream',
                     as_attachment=True,
                     attachment_filename=f'vmi_{vmi_version.id}_{vmi_version.hash}.ova')


def parse_definition(definition_file, vmi_hash: str):
    validator = Validator(vmi_schema)

    try:
        definition = yaml.safe_load(definition_file)
        normalized_definition = validator.normalized(definition)

        if validator.errors:
            raise Exception(validator.errors)

    except Exception as e:
        raise BadRequest(e.__str__())

    return create_vmi(normalized_definition, vmi_hash)
