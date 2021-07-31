import enum
import uuid
from datetime import datetime
from typing import List

from sqlalchemy.dialects.postgresql import UUID

from psma.extensions import db


class ModuleType(enum.Enum):
    data_collection = 0
    data_processing = 1


class ModuleVersion(db.Model):
    id = db.Column(UUID(as_uuid=True), db.ForeignKey('module.id'))
    hash = db.Column(db.String(64), nullable=False)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    comment = db.Column(db.String(256), default='')

    __table_args__ = (db.PrimaryKeyConstraint('id', 'hash'),)


class Module(db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(64), unique=True, nullable=False)
    type = db.Column(db.Enum(ModuleType), nullable=False)


module_schema = {
    'module': {
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
                'allowed': [member.name for member in ModuleType]
            },
            'comment': {
                'required': False,
                'type': 'string'
            }
        }
    }
}


def create_module(module_object, module_hash: str):
    module = Module(id=uuid.uuid4(), name=module_object['module']['name'],
                    type=ModuleType[module_object['module']['type']])
    module_version = ModuleVersion(id=module.id, hash=module_hash, comment=module_object['module']['comment'])
    return module, module_version


def create_module_yaml(module: Module, module_versions: List[ModuleVersion]):
    return {
        'module': {
            'id': str(module.id),
            'name': module.name,
            'type': module.type.name,
            'versions': [
                {
                    'hash': module_version.hash,
                    'timestamp': module_version.timestamp,
                    'comment': module_version.comment
                } for module_version in module_versions
            ]
        }
    }


def create_module_version_yaml(module: Module, module_version: ModuleVersion):
    return {
        'module': {
            'id': str(module.id),
            'name': module.name,
            'type': module.type.name,
            'version': {
                'hash': module_version.hash,
                'timestamp': module_version.timestamp,
                'comment': module_version.comment
            }
        }
    }
