import ast
import enum
import uuid
from datetime import datetime
from typing import List

from sqlalchemy import ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID

from psma.extensions import db
from psma.models.module import ModuleVersion
from psma.models.vmi import VMIVersion


class ExperimentStatus(enum.Enum):
    NOT_STARTED = 0
    COLLECTING_DATA = 1
    PROCESSING_DATA = 2
    FINISHED = 3


class ExperimentSampleStatus(enum.Enum):
    NOT_STARTED = 0
    COLLECTING_DATA = 1
    DATA_COLLECTED = 2


class ExperimentSample(db.Model):
    id = db.Column(UUID(as_uuid=True), db.ForeignKey('experiment.id'))
    hash = db.Column(db.String(64), nullable=False)

    original_name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.Enum(ExperimentSampleStatus), nullable=False, default=ExperimentSampleStatus.NOT_STARTED)

    __table_args__ = (db.PrimaryKeyConstraint('id', 'hash'),)


class Experiment(db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = db.Column(db.Enum(ExperimentStatus), nullable=False, default=ExperimentStatus.NOT_STARTED)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    username = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255), nullable=False)

    unzip_command = db.Column(db.String(255), nullable=False)
    unzip_args = db.Column(db.String(255), default='[]')

    working_directory = db.Column(db.String(255), nullable=False)
    allowed_time = db.Column(db.INTEGER, default=60)

    vmi_id = db.Column(UUID(as_uuid=True), nullable=False)
    vmi_hash = db.Column(db.String(64), nullable=False)

    dcs_module_id = db.Column(UUID(as_uuid=True), nullable=False)
    dcs_module_hash = db.Column(db.String(64), nullable=False)
    dcs_module_entrypoint = db.Column(db.String(255), nullable=True)
    dcs_module_args = db.Column(db.String(255), default='[]')

    dps_module_id = db.Column(UUID(as_uuid=True), nullable=False)
    dps_module_hash = db.Column(db.String(64), nullable=False)
    dps_module_args = db.Column(db.String(255), default='[]')

    __table_args__ = (ForeignKeyConstraint((vmi_id, vmi_hash),
                                           (VMIVersion.id, VMIVersion.hash)),
                      ForeignKeyConstraint((dcs_module_id, dcs_module_hash),
                                           (ModuleVersion.id, ModuleVersion.hash)),
                      ForeignKeyConstraint((dps_module_id, dps_module_hash),
                                           (ModuleVersion.id, ModuleVersion.hash)))


experiment_schema = {
    'experiment': {
        'required': True,
        'type': 'dict',
        'schema': {
            'id': {
                'required': False,
                'type': 'uuid',
                'default_setter': lambda _: uuid.uuid4()
            },
            'timestamp': {
                'required': False,
                'type': 'datetime',
                'default_setter': lambda _: datetime.now()
            },
            'credentials': {
                'required': True,
                'type': 'dict',
                'schema': {
                    'username': {
                        'required': True,
                        'type': 'string'
                    },
                    'password': {
                        'required': True,
                        'type': 'string'
                    }
                }
            },
            'unzip': {
                'required': True,
                'type': 'dict',
                'schema': {
                    'command': {
                        'required': True,
                        'type': 'string'
                    },
                    'args': {
                        'required': False,
                        'type': 'list',
                        'default': []
                    }
                }
            },
            'working_directory': {
                'required': True,
                'type': 'string'
            },
            'allowed_time': {
                'required': False,
                'type': 'integer',
                'default': 60
            },
            'vmi': {
                'required': True,
                'type': 'dict',
                'schema': {
                    'id': {
                        'required': True,
                        'type': 'uuid'
                    },
                    'hash': {
                        'required': False,
                        'type': 'string',
                        'default': None
                    }
                }
            },
            'dcs_module': {
                'required': True,
                'type': 'dict',
                'schema': {
                    'id': {
                        'required': True,
                        'type': 'uuid'
                    },
                    'hash': {
                        'required': False,
                        'type': 'string',
                        'default': None
                    },
                    'entrypoint': {
                        'required': False,
                        'type': 'string',
                        'default': 'entrypoint.bat'
                    },
                    'args': {
                        'required': False,
                        'type': 'list',
                        'default': []
                    }
                }
            },
            'dps_module': {
                'required': True,
                'type': 'dict',
                'schema': {
                    'id': {
                        'required': True,
                        'type': 'uuid'
                    },
                    'hash': {
                        'required': False,
                        'type': 'string',
                        'default': None
                    },
                    'args': {
                        'required': False,
                        'type': 'list',
                        'default': []
                    }
                }
            }
        }
    }
}


def create_experiment(experiment_object):
    return Experiment(id=uuid.uuid4(),
                      username=experiment_object['experiment']['credentials']['username'],
                      password=experiment_object['experiment']['credentials']['password'],
                      unzip_command=str(experiment_object['experiment']['unzip']['command']),
                      unzip_args=str(experiment_object['experiment']['unzip']['args']),
                      working_directory=str(experiment_object['experiment']['working_directory']),
                      allowed_time=experiment_object['experiment']['allowed_time'],
                      vmi_id=experiment_object['experiment']['vmi']['id'],
                      vmi_hash=experiment_object['experiment']['vmi']['hash'],
                      dcs_module_id=experiment_object['experiment']['dcs_module']['id'],
                      dcs_module_hash=experiment_object['experiment']['dcs_module']['hash'],
                      dcs_module_entrypoint=str(experiment_object['experiment']['dcs_module']['entrypoint']),
                      dcs_module_args=str(experiment_object['experiment']['dcs_module']['args']),
                      dps_module_id=experiment_object['experiment']['dps_module']['id'],
                      dps_module_hash=experiment_object['experiment']['dps_module']['hash'],
                      dps_module_args=str(experiment_object['experiment']['dps_module']['args']))


def create_experiment_yaml(experiment: Experiment, samples: List[ExperimentSample]):
    return {
        'experiment': {
            'id': str(experiment.id),
            'timestamp': experiment.timestamp,
            'credentials': {
                'username': experiment.username,
                'password': experiment.password
            },
            'unzip': {
                'command': experiment.unzip_command,
                'args': ast.literal_eval(experiment.unzip_args)
            },
            'working_directory': experiment.working_directory,
            'allowed_time': experiment.allowed_time,
            'vmi': {
                'id': str(experiment.vmi_id),
                'hash': experiment.vmi_hash
            },
            'dcs_module': {
                'id': str(experiment.dcs_module_id),
                'hash': experiment.dcs_module_hash,
                'entrypoint': experiment.dcs_module_entrypoint,
                'args': ast.literal_eval(experiment.dcs_module_args)
            },
            'dps_module': {
                'id': str(experiment.dps_module_id),
                'hash': experiment.dps_module_hash,
                'args': ast.literal_eval(experiment.dps_module_args)
            },
            'status': experiment.status.name,
            'samples': [
                {
                    'original_name': sample.original_name,
                    'hash': sample.hash,
                    'status': sample.status.name
                } for sample in samples
            ]
        }
    }


def update_experiment_status(experiment: Experiment, status: ExperimentStatus):
    if experiment.status is not status:
        experiment.status = status
        db.session.commit()


def update_sample_status(experiment: Experiment, sample_hash: str, status: ExperimentSampleStatus):
    experiment_sample = ExperimentSample.query.filter_by(id=experiment.id, hash=sample_hash).first()
    if experiment_sample is None:
        raise RuntimeError(
            f'Illegal state: Trying to execute not found sample {sample_hash} in experiment {experiment.id}')

    if experiment_sample.status is not status:
        experiment_sample.status = status
        db.session.commit()
