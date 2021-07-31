from flask_sqlalchemy import SQLAlchemy

from psma.common.sftp_controller import SFTPController
from psma.workers.celery_app import CeleryApp

db = SQLAlchemy()
sftp_controller = SFTPController()
celery_app = CeleryApp()
