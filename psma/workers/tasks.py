import logging
from types import TracebackType
from typing import List

from celery import chord

from psma.dcs import create_vm_controller
from psma.dcs.vm_controller import VMController
from psma.dps.docker_controller import DockerController
from psma.extensions import celery_app
from psma.models.experiment import Experiment, ExperimentSample, update_experiment_status, ExperimentStatus, \
    ExperimentSampleStatus, update_sample_status


@celery_app.task(time_limit=500, soft_time_limit=300)
def collect(experiment_id, sample_hash):
    print(f'Collect: {experiment_id}, {sample_hash}')

    experiment = Experiment.query.filter_by(id=experiment_id).first()
    if experiment is None:
        raise RuntimeError(f'Not found error: Experiment with id: {experiment_id} not found')

    update_experiment_status(experiment, ExperimentStatus.COLLECTING_DATA)
    update_sample_status(experiment, sample_hash, ExperimentSampleStatus.COLLECTING_DATA)

    vm_controller: VMController = create_vm_controller(experiment)

    try:
        vm_controller.power_up()
        vm_controller.analyse(sample_hash)
        vm_controller.power_down()
        return True
    except Exception as e:
        logging.error(e)
        return False
    finally:
        try:
            vm_controller.upload_data(sample_hash)
            vm_controller.clean_env(sample_hash)
            update_sample_status(experiment, sample_hash, ExperimentSampleStatus.DATA_COLLECTED)
        except Exception as e:
            logging.error(e)
            return False


@celery_app.task()
def process(results: List[bool], experiment_id: str, samples: List[str]):
    print(f'Process: {experiment_id} | results: {results}')

    experiment = Experiment.query.filter_by(id=experiment_id).first()
    if experiment is None:
        raise RuntimeError(f'Not found error: Experiment with id: {experiment_id} not found')

    update_experiment_status(experiment, ExperimentStatus.PROCESSING_DATA)

    docker_controller: DockerController = DockerController(experiment)

    try:
        docker_controller.load_collected_data(samples)
        return docker_controller.process()
    except Exception as e:
        logging.error(e)
        return False
    finally:
        try:
            docker_controller.upload_result()
            docker_controller.clean_env()
            update_experiment_status(experiment, ExperimentStatus.FINISHED)
        except Exception as e:
            logging.error(e)
            return False


def launch_experiment(experiment: Experiment, samples: List[ExperimentSample]):
    experiment_entry = chord(
        [collect.s(str(experiment.id), sample.hash) for sample in samples]
    )(
        process.s(str(experiment.id), [sample.hash for sample in samples]),
        task_id=str(experiment.id)
    )

    return experiment_entry
