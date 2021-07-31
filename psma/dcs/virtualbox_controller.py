import ast
import logging
import os
import time
import uuid
from typing import Optional, List

import virtualbox
from oslo_concurrency import lockutils
from virtualbox import library_ext
from virtualbox.library import CloneMode, VBoxErrorInvalidObjectState, VBoxErrorObjectNotFound, CloneOptions, GuestSessionWaitForFlag
from virtualbox.library_ext import IGuestSession, ISession, IProgress

from psma.dcs.vm_controller import VMController
from psma.models.experiment import Experiment
from psma.models.vmi import VMI, VMIVersion


class IMachine(library_ext.IMachine):

    def launch_vm_process(self, session=None, type_p="headless", environment=""):
        if session is None:
            local_session = virtualbox.library.ISession()
        else:
            local_session = session

        progress = self._call("launchVMProcess", in_p=[local_session, type_p, environment])

        progress = IProgress(progress)

        if session is None:
            progress.wait_for_completion(-1)
            local_session.unlock_machine()
        return progress


class VirtualboxController(VMController):

    def __init__(self, experiment: Experiment, vmi: VMI, vmi_version: VMIVersion):
        super().__init__(experiment, vmi, vmi_version)
        self.vbox = virtualbox.VirtualBox()
        self.session: Optional[ISession] = None
        self.guest_session: Optional[IGuestSession] = None
        self.machine: Optional[IMachine] = None
        self.machine_id: Optional[str] = None

    def power_up(self):
        self.machine = self.clone_machine()
        self.session = self.power_up_vm()

    def power_down(self):
        self.power_down_vm()

    def analyse(self, sample_hash: str):
        self.guest_session = self.upload_files_to_vm(sample_hash)
        self.extract_files()
        self.execute_dcs_entrypoint()
        time.sleep(self.experiment.allowed_time)
        self.get_data_from_vm()

    def upload_data(self, sample_hash: str):
        self.upload_machine_data(self.machine_id, sample_hash)

    def clean_env(self, sample_hash: str):
        self.delete_vm()
        self.clean_vmi_folder(self.machine_id)
        self.sftp_controller.file_delete(f'experiment/{self.experiment.id}/samples/{sample_hash}')
        self.sftp_controller.close_connection()

    def import_machine(self) -> None:
        machine_compressed_id = VMController.compress_machine_name(self.vmi.id, self.vmi_version.hash)
        machine_ids = [machine.name for machine in self.vbox.machines]
        if machine_compressed_id in machine_ids:
            return

        self.download_machine()

        appliance = self.vbox.create_appliance()
        appliance.read(os.path.join(self.cwd, f'{machine_compressed_id}.ova'))
        description = appliance.find_description(self.vmi.name)
        description.set_name(machine_compressed_id)
        progress = appliance.import_machines()
        progress.wait_for_completion()

        self.delete_vmi_file()

        if machine_compressed_id not in [machine.name for machine in self.vbox.machines]:
            raise RuntimeError(f'Error finding machine {machine_compressed_id} after importing')

    @lockutils.synchronized('vmi_machines_lock', external=True)
    def clone_machine(self) -> IMachine:

        self.import_machine()

        original_machine_id = VMController.compress_machine_name(self.vmi.id, self.vmi_version.hash)
        clone_machine_id = VMController.compress_machine_name(self.experiment.id, uuid.uuid4().hex)

        machine = self.vbox.find_machine(original_machine_id)
        session = virtualbox.Session()

        machine.lock_machine(session, virtualbox.library.LockType.shared)

        try:
            session.machine.find_snapshot('to_clone')
            snapshot_taken = True
        except VBoxErrorObjectNotFound:
            snapshot_taken = False

        if not snapshot_taken:
            progress = session.machine.take_snapshot('to_clone', 'to_clone', pause=False)[0]
            progress.wait_for_completion(600000)  # SNAPSHOT TIMEOUT: 10m

        session.machine.clone(
            snapshot_name_or_id='to_clone',
            name=clone_machine_id,
            mode=CloneMode.machine_state,
            options=[CloneOptions.link]
        )

        session.unlock_machine()

        if clone_machine_id not in [machine.name for machine in self.vbox.machines]:
            raise RuntimeError(f'Error finding machine {clone_machine_id} after cloning from {original_machine_id}')

        self.machine_id = clone_machine_id
        return IMachine(self.vbox.find_machine(clone_machine_id))

    def power_up_vm(self) -> ISession:

        if self.machine.state < virtualbox.library.MachineState.running:
            progress = self.machine.launch_vm_process()
            progress.wait_for_completion(60000)  # POWER UP TIMEOUT: 1m
            return self.machine.create_session()

        raise RuntimeError(f'Machine {self.machine_id} already running when trying to power up')

    def power_down_vm(self) -> None:

        max_wait = 60  # POWER DOWN TIMEOUT: 1m
        waited = 0

        if self.machine.state >= virtualbox.library.MachineState.running:
            self.session.console.power_down()
            while self.machine.state >= virtualbox.library.MachineState.running and waited < max_wait:
                time.sleep(1)
                waited += 1

            if waited == max_wait:
                raise RuntimeError(f'Machine {self.machine_id} took to much time powering down')

    def upload_files_to_vm(self, sample_hash: str) -> IGuestSession:

        self.download_files(self.machine_id, sample_hash)
        self.zip_files_for_upload(self.machine_id)

        guest_session: IGuestSession = self.session.console.guest.create_session(
            self.experiment.username, self.experiment.password, timeout_ms=self.experiment.allowed_time * 1000
        )

        progress = guest_session.file_copy_to_guest(
            os.path.join(self.cwd, f'{self.machine_id}.zip'),
            fr'{self.experiment.working_directory}\files.zip',
            []
        )
        progress.wait_for_completion(10000)  # COPY TIMEOUT: 10s

        return guest_session

    def extract_files(self) -> None:

        working_dir_fixed_for_eval = self.experiment.working_directory.replace('\\', '\\\\')

        parsed_command = self.experiment.unzip_command.replace("$WORK_DIR", self.experiment.working_directory)
        parsed_args = self.experiment.unzip_args.replace("$WORK_DIR", working_dir_fixed_for_eval)

        files_parsed_command = parsed_command.replace("$ZIP_FILE", f'{self.experiment.working_directory}\\files.zip')
        module_parsed_command = parsed_command.replace("$ZIP_FILE",
                                                       f'{self.experiment.working_directory}\\files\\module.zip')

        files_parsed_args = parsed_args.replace("$ZIP_FILE", f'{working_dir_fixed_for_eval}\\\\files.zip')
        module_parsed_args = parsed_args.replace("$ZIP_FILE", f'{working_dir_fixed_for_eval}\\\\files\\\\module.zip')

        self.execute_command_on_vm(files_parsed_command, ast.literal_eval(files_parsed_args))
        self.execute_command_on_vm(module_parsed_command, ast.literal_eval(module_parsed_args))

    def execute_dcs_entrypoint(self):
        self.execute_command_on_vm(
            fr'{self.experiment.working_directory}\files\{self.experiment.dcs_module_entrypoint}',
            ast.literal_eval(self.experiment.dcs_module_args), async_call=False)

    def execute_command_on_vm(self, command: str, args: List[str], async_call: bool = False):

        p, o, e = self.guest_session.execute(command, args, timeout_ms=2000)  # COMMAND TIMEOUT: 20s
        if o:
            logging.info(f'COMMAND: {command} {args} || {o}')
        if e:
            logging.error(f'COMMAND: {command} {args} || {e}')

    def get_data_from_vm(self):

        if self.machine.state < virtualbox.library.MachineState.running:
            progress = self.machine.launch_vm_process()
            progress.wait_for_completion(60000)  # POWER UP TIMEOUT: 1m
            self.session = self.machine.create_session()

            self.guest_session = self.session.console.guest.create_session(
                self.experiment.username, self.experiment.password, timeout_ms=self.experiment.allowed_time * 1000
            )

        collected_data_folder = os.path.join(self.cwd, self.machine_id, 'collected_data')
        collected_data_file = os.path.join(self.cwd, self.machine_id, 'collected_data', 'collected_data')
        os.mkdir(collected_data_folder)

        progress = self.guest_session.file_copy_from_guest(
            fr'{self.experiment.working_directory}\collected_data',
            str(collected_data_file),
            []
        )
        progress.wait_for_completion(20000)  # COPY TIMEOUT: 20s

        with open(collected_data_file, 'a+') as fp:
            pass

    def delete_vm(self) -> None:
        if self.machine is None:
            return

        max_wait = 60  # REMOVE TIMEOUT: 1m
        waited = 0

        while waited < max_wait:
            try:
                self.machine.remove(delete=True)
                break
            except VBoxErrorInvalidObjectState as vbeios:
                logging.error(f'Caught VBoxErrorInvalidObjectState: {vbeios}')
                time.sleep(1)
                waited += 1

        if waited == max_wait:
            raise RuntimeError(f'Machine {self.machine_id} took to much time removing')

        else:
            self.machine = None
            if self.machine_id in [machine.name for machine in self.vbox.machines]:
                raise RuntimeError(f'Unsuccessfully deleted machine {self.machine_id}')
