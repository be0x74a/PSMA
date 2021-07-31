from psma import create_app
from psma.workers.celery_app import CeleryApp

flask_app = create_app()
celery_app = CeleryApp()
celery_app.init_app(flask_app)
