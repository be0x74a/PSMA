from distutils import util
import os


class BaseDefaultConfigs(object):
    DEBUG = True

    SFTP_HOST = os.getenv('SFTP_HOST', 'sftp')
    SFTP_PORT = os.getenv('SFTP_PORT', 22)
    SFTP_BASE = os.getenv('SFTP_BASE', 'storage')
    SFTP_USER = os.getenv('SFTP_USER', 'psma')
    SFTP_PASS = os.getenv('SFTP_PASS')

    PSQL_HOST = os.getenv('PSQL_HOST', 'db')
    PSQL_DB = os.getenv('PSQL_DB', 'psma_db')
    PSQL_USER = os.getenv('PSQL_USER', 'psma')
    PSQL_PASS = os.getenv('PSQL_PASS')

    REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
    REDIS_PORT = os.getenv('REDIS_PORT', 6379)
    REDIS_DB = os.getenv('REDIS_DB', 0)
    REDIS_PASS = os.getenv('REDIS_PASS')

    CLEAN_ENV = os.getenv('CLEAN_ENV', "False")


class CompoundConfigs(object):

    def __init__(self, app_configs):
        self.SQLALCHEMY_DATABASE_URI = f'postgresql://{app_configs["PSQL_USER"]}:{app_configs["PSQL_PASS"]}@{app_configs["PSQL_HOST"]}/{app_configs["PSQL_DB"]}'
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False
        self.SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
        }
        self.JSONIFY_PRETTYPRINT_REGULAR = True
        self.CELERY_BROKER_URL = f'redis://:{app_configs["REDIS_PASS"]}@{app_configs["REDIS_HOST"]}:{app_configs["REDIS_PORT"]}/{app_configs["REDIS_DB"]}'
        self.CELERY_BACKEND_URL = f'redis://:{app_configs["REDIS_PASS"]}@{app_configs["REDIS_HOST"]}:{app_configs["REDIS_PORT"]}/{app_configs["REDIS_DB"]}'
        self.CLEAN_ENV = bool(util.strtobool(app_configs['CLEAN_ENV']))
