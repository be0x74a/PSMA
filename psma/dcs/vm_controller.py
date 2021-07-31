import hashlib
import os
import shutil
from io import BytesIO
from pathlib import Path
from tempfile import mkdtemp

from psma.common.sftp_controller import SFTPController
from psma.extensions import sftp_controller
from psma.models.experiment import Experiment, ExperimentSample
from psma.models.vmi import VMI, VMIVersion


class VMController:
    def __init__(self, experiment: Experiment, vmi: VMI, vmi_version: VMIVersion):
        self.cwd = os.getenv('DCS_CWD', mkdtemp())
        self.experiment = experiment
        self.vmi = vmi
        self.vmi_version = vmi_version

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

    def power_up(self):
        pass

    def analyse(self, sample: ExperimentSample):
        pass

    def power_down(self):
        pass

    def clean_env(self, sample_hash: str):
        pass

    def upload_data(self, sample_hash):
        pass

    def upload_machine_data(self, machine_id: str, sample_hash: str):
        collected_data = os.path.join(self.cwd, machine_id, 'collected_data', 'collected_data')
        with open(collected_data, 'rb') as data:
            self.sftp_controller.folder_create(f'experiment/{self.experiment.id}/collected/{sample_hash}')
            data_bytes = BytesIO(data.read())
            self.sftp_controller.file_create(
                data_bytes,
                f'experiment/{self.experiment.id}/collected/{sample_hash}/collected_data')

    def download_machine(self):
        local_file_path = Path(
            os.path.join(self.cwd,
                         f'{VMController.compress_machine_name(self.vmi.id, self.vmi_version.hash)}.ova'))
        self.sftp_controller.file_download(f'vmi/{self.vmi.id}/{self.vmi_version.hash}',
                                           str(local_file_path.absolute()))

    def delete_vmi_file(self):
        local_file_path = Path(
            os.path.join(self.cwd,
                         f'{VMController.compress_machine_name(self.vmi.id, self.vmi_version.hash)}.ova'))
        local_file_path.unlink()

    def download_files(self, machine_id: str, sample_hash: str):
        machine_folder = Path(os.path.join(self.cwd, machine_id))
        os.mkdir(machine_folder)

        self.sftp_controller.file_download(
            f'module/{self.experiment.dcs_module_id}/{self.experiment.dcs_module_hash}',
            str(machine_folder.joinpath('module.zip').absolute())
        )
        self.sftp_controller.file_download(
            f'experiment/{self.experiment.id}/samples/{sample_hash}',
            str(machine_folder.joinpath('sample').absolute())
        )

    def zip_files_for_upload(self, machine_id: str):
        machine_folder = os.path.join(self.cwd, machine_id)
        shutil.make_archive(machine_folder, 'zip', machine_folder)

    def clean_vmi_folder(self, machine_id):
        if machine_id is not None:
            Path(os.path.join(self.cwd, f'{machine_id}.zip')).unlink()
            shutil.rmtree(Path(os.path.join(self.cwd, machine_id), ignore_errors=True))

    @staticmethod
    def compress_machine_name(machine_prefix: str, machine_suffix: str):
        return hashlib.md5(f'{machine_prefix}_{machine_suffix}'.encode()).hexdigest()
