import click
from flask.cli import with_appcontext

from psma.extensions import db, sftp_controller


@click.command(name='create_initial_state')
@with_appcontext
def create_initial_state():
    _create_initial_state()


@click.command(name='clear_state')
@with_appcontext
def clear_state():
    _clear_state()


def _create_initial_state():
    db.create_all()
    sftp_controller.folder_create('vmi', passive=True)
    sftp_controller.folder_create('module', passive=True)
    sftp_controller.folder_create('experiment', passive=True)


def _clear_state():
    db.drop_all()
    sftp_controller.folder_delete('vmi')
    sftp_controller.folder_delete('module')
    sftp_controller.folder_delete('experiment')
