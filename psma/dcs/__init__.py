from psma.dcs.vm_controller import VMController
from psma.models.experiment import Experiment
from psma.models.vmi import VMI, VMIVersion, VMIType
from .virtualbox_controller import VirtualboxController


def create_vm_controller(experiment: Experiment) -> VMController:
    vmi = VMI.query.filter_by(id=experiment.vmi_id).first()
    if vmi is None:
        raise RuntimeError(f'VMI with id {experiment.vmi_id} was not found.')

    vmi_version = VMIVersion.query.filter_by(id=experiment.vmi_id, hash=experiment.vmi_hash).first()
    if vmi_version is None:
        raise RuntimeError(f'VMI version with id {experiment.vmi_id} and hash {experiment.vmi_hash} was not found')

    if vmi.type is VMIType.virtualbox:
        return VirtualboxController(experiment, vmi, vmi_version)
    else:
        raise RuntimeError(f'Unsupported VMI type {vmi.type} in current version of the system')
