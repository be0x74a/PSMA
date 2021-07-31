import logging
from stat import S_ISDIR
from typing import IO

from paramiko import Transport
from paramiko.sftp_client import SFTPClient
from paramiko.sftp_file import SFTPFile


class SFTPController:
    def setup_controller(self, host, port, user, key, base_dir):
        self.host = host
        self.port = int(port)
        self.user = user
        self.key = key
        self.base_dir = base_dir

        if self.host and self.port and self.user and self.key and self.base_dir:
            self.transport = Transport((self.host, self.port))
            self.transport.connect(username=self.user, password=self.key)
            self.client = SFTPClient.from_transport(self.transport)
            self.client.chdir(self.base_dir)

    def __init__(self, **kwargs):
        self.host = None
        self.port = None
        self.user = None
        self.key = None
        self.base_dir = None
        self.transport = None
        self.client = None

        if kwargs.get('host') \
                and kwargs.get('port') \
                and kwargs.get('user') \
                and kwargs.get('key') \
                and kwargs.get('base_dir'):
            self.setup_controller(kwargs.get('host'), kwargs.get('port'), kwargs.get('user'), kwargs.get('key'),
                                  kwargs.get('base_dir'))

    def init_app(self, flask_app):
        host = flask_app.config.get('SFTP_HOST')
        port = flask_app.config.get('SFTP_PORT')
        user = flask_app.config.get('SFTP_USER')
        key = flask_app.config.get('SFTP_PASS')
        base_dir = flask_app.config.get('SFTP_BASE')

        self.setup_controller(host, port, user, key, base_dir)

    # CRD file operations
    def file_create(self, file: IO[bytes], file_name: str):
        self._check_connection()
        file.seek(0)
        self.client.putfo(file, file_name, confirm=True)

    def file_delete(self, file_name: str):
        self._check_connection()
        self.client.remove(file_name)

    def file_read(self, file_name: str) -> SFTPFile:
        self._check_connection()
        return self.client.file(file_name, 'r')

    def file_download(self, remote_file_path: str, local_file_path: str):
        self._check_connection()
        logging.info(f'Downloading {remote_file_path} to {local_file_path}')
        return self.client.get(remote_file_path, local_file_path)

    # CD folder operations
    def folder_create(self, folder_name: str, passive=False):
        self._check_connection()
        try:
            self.client.mkdir(folder_name)
        except Exception as e:
            if not passive:
                raise e

    def folder_delete(self, folder_name: str):
        self._check_connection()

        files = self.client.listdir(path=folder_name)

        for f in files:
            filepath = f'{folder_name}/{f}'
            if self.folder_exists(filepath):
                self.folder_delete(filepath)
            else:
                self.client.remove(filepath)

        self.client.rmdir(folder_name)

    def close_connection(self):
        self._check_connection()
        self.client.close()
        self.transport.close()

    def folder_exists(self, path):
        try:
            return S_ISDIR(self.client.stat(path).st_mode)
        except IOError:
            return False

    def _check_connection(self):
        if not self.transport.is_active():
            self.transport = Transport(self.host, self.port)
            self.transport.connect(username=self.user, pkey=self.key)
            self.client = SFTPClient.from_transport(self.transport)
            self.client.chdir(self.base_dir)
