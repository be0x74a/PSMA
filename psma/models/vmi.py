import enum
import uuid
from datetime import datetime
from typing import List

from sqlalchemy.dialects.postgresql import UUID

from psma.extensions import db


class VMIType(enum.Enum):
    virtualbox = 0


class VMIVersion(db.Model):
    id = db.Column(UUID(as_uuid=True), db.ForeignKey('vmi.id'))
    hash = db.Column(db.String(64), nullable=False)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    comment = db.Column(db.String(256), default='')

    __table_args__ = (db.PrimaryKeyConstraint('id', 'hash'),)


class VMI(db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(64), unique=True, nullable=False)
    type = db.Column(db.Enum(VMIType), nullable=False)

    __tablename__ = "vmi"


vmi_schema = {
    'vmi': {
        'required': True,
        'type': 'dict',
        'schema': {
            'name': {
                'required': True,
                'type': 'string'
            },
            'type': {
                'required': True,
                'type': 'string',
                'allowed': [member.name for member in VMIType]
            },
            'comment': {
                'required': False,
                'type': 'string'
            }
        }
    }
}


def create_vmi(vmi_object, vmi_hash: str):
    import json
    print(json.dumps(vmi_object))
    vmi = VMI(id=uuid.uuid4(), name=vmi_object['vmi']['name'], type=VMIType[vmi_object['vmi']['type']])
    vmi_version = VMIVersion(id=vmi.id, hash=vmi_hash, comment=vmi_object['vmi']['comment'])
    return vmi, vmi_version


def create_vmi_yaml(vmi: VMI, vmi_versions: List[VMIVersion]):
    return {
        'vmi': {
            'id': str(vmi.id),
            'name': vmi.name,
            'type': vmi.type.name,
            'versions': [
                {
                    'hash': vmi_version.hash,
                    'timestamp': vmi_version.timestamp,
                    'comment': vmi_version.comment
                } for vmi_version in vmi_versions
            ]
        }
    }


def create_vmi_version_yaml(vmi: VMI, vmi_version: VMIVersion):
    return {
        'vmi': {
            'id': str(vmi.id),
            'name': vmi.name,
            'type': vmi.type.name,
            'version': {
                'hash': vmi_version.hash,
                'timestamp': vmi_version.timestamp,
                'comment': vmi_version.comment
            }
        }
    }
