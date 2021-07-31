from flask import Flask

from psma import extensions
from psma.commands import _create_initial_state, _clear_state, create_initial_state, clear_state
from psma.configs import BaseDefaultConfigs, CompoundConfigs
from psma.routes.v1 import vmi, module, experiment
from psma.routes import home


def create_app():
    app = Flask(__name__)
    app.config.from_object(BaseDefaultConfigs())
    app.config.from_envvar('PSMA_CONFIG_FILE', silent=True)
    app.config.from_object(CompoundConfigs(app.config))

    extensions.db.init_app(app)
    extensions.sftp_controller.init_app(app)
    extensions.celery_app.init_app(app)

    app.register_blueprint(vmi.blueprint)
    app.register_blueprint(module.blueprint)
    app.register_blueprint(experiment.blueprint)
    app.register_blueprint(home.blueprint)
    app.cli.add_command(create_initial_state)
    app.cli.add_command(clear_state)

    if app.config['CLEAN_ENV']:
        with app.app_context():
            _create_initial_state()
            _clear_state()
            _create_initial_state()

    return app
