from celery import Celery


class CeleryApp(Celery):

    def init_app(self, app):
        self.main = app.import_name
        self.conf.update(
            broker_url=app.config['CELERY_BROKER_URL'],
            result_backend=app.config['CELERY_BACKEND_URL'],
            worker_send_task_events=True,
            task_send_sent_event=True
        )

        self.conf.update(
            task_routes={
                'psma.workers.tasks.collect': {'queue': 'dcs'},
                'psma.workers.tasks.process': {'queue': 'dps'},
            }
        )

        self.conf.update(app.config)

        class ContextTask(self.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        self.Task = ContextTask
