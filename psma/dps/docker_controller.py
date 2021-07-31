import os
import zipfile
from io import BytesIO
from pathlib import Path
from tempfile import mkdtemp
from typing import List, Optional

import docker as docker
from docker.models.containers import Container
from docker.models.images import Image

from psma.common.sftp_controller import SFTPController
from psma.extensions import sftp_controller
from psma.models.experiment import Experiment
from psma.models.module import Module, ModuleVersion, ModuleType


class DockerController:
    def __init__(self, experiment: Experiment):
        self.cwd = os.getenv('DPS_CWD', mkdtemp())
        self.experiment = experiment
        self.docker_client = docker.from_env()
        self.image: Optional[Image] = None
        self.container: Optional[Container] = None

        dps_module = Module.query.filter_by(id=experiment.dps_module_id).first()
        if dps_module is None:
            raise RuntimeError(f'DPS Module with id {experiment.dps_module_id} was not found.')

        dps_module_version = ModuleVersion.query.filter_by(id=experiment.dps_module_id,
                                                           hash=experiment.dps_module_hash).first()
        if dps_module_version is None:
            raise RuntimeError(
                f'DPS Module version with id {experiment.dps_module_id} and hash {experiment.dps_module_hash} was not found')

        if dps_module.type is not ModuleType.data_processing:
            raise RuntimeError(f'Module type {dps_module.type} should be {ModuleType.data_processing.name}')

        # Have to create new controller else paramiko hangs
        self.sftp_controller = SFTPController(
            host=sftp_controller.host,
            port=sftp_controller.port,
            user=sftp_controller.user,
            key=sftp_controller.key,
            base_dir=sftp_controller.base_dir
        )

        if not Path(self.cwd).exists():
            os.mkdir(self.cwd)

        os.mkdir(os.path.join(self.cwd, str(self.experiment.id)))
        dps_module_folder = os.path.join(self.cwd, str(self.experiment.id), 'container')
        os.mkdir(dps_module_folder)
        dps_module_path = Path(os.path.join(self.cwd, str(self.experiment.id), 'container', 'dps_module.zip'))

        self.sftp_controller.file_download(
            f'module/{self.experiment.dps_module_id}/{self.experiment.dps_module_hash}',
            str(dps_module_path.absolute())
        )

        with zipfile.ZipFile(dps_module_path, 'r') as zip_ref:
            zip_ref.extractall(dps_module_folder)

        dps_module_path.unlink()
        self.image, _ = self.docker_client.images.build(path=dps_module_folder)

    def load_collected_data(self, samples: List[str]):
        os.mkdir(os.path.join(self.cwd, str(self.experiment.id), 'collected_data'))

        for sample_hash in samples:
            self.sftp_controller.file_download(
                f'experiment/{self.experiment.id}/collected/{sample_hash}/collected_data',
                str(Path(os.path.join(self.cwd, str(self.experiment.id), 'collected_data', sample_hash)).absolute())
            )

    def process(self) -> int:
        self.container = self.docker_client.containers.run(self.image,
                                                           detach=True,
                                                           volumes={
                                                               os.path.join(self.cwd, str(self.experiment.id)): {
                                                                   'bind': '/psma',
                                                                   'mode': 'rw'
                                                               }
                                                           })
        return self.container.wait()["StatusCode"]

    def upload_result(self):
        result_file = os.path.join(self.cwd, str(self.experiment.id), 'result.zip')

        # Create if not exist
        if not os.path.isfile(result_file):
            with open(result_file, 'a+') as data:
                pass

        with open(result_file, 'rb') as data:
            result_bytes = BytesIO(data.read())
            self.sftp_controller.file_create(
                result_bytes,
                f'experiment/{self.experiment.id}/result.zip')

    def clean_env(self):
        self.container.remove()
        self.docker_client.images.remove(self.image.short_id, force=True)
        self.sftp_controller.folder_delete(f'experiment/{self.experiment.id}/samples/')
        self.sftp_controller.folder_delete(f'experiment/{self.experiment.id}/collected/')
