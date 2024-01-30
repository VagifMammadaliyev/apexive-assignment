from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ontime.settings")

app = Celery("ontime")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


class QUEUES:
    CUSTOMS = "customs"
    NOTIFICATIONS = "notifications"


app.conf.beat_schedule = {
    "central_bank_fetch_currencies": {
        "task": "core.tasks.fetch_currency_rates",
        "schedule": crontab(
            minute="15", hour="6", day_of_month="*", month_of_year="*", day_of_week="*"
        ),
    },
    "refresh_package_states": {
        "task": "fulfillment.tasks.refresh_declared_packages",
        "schedule": crontab(
            minute="*/15",
            hour="*",
            day_of_month="*",
            month_of_year="*",
            day_of_week="*",
        ),
        "options": {"queue": QUEUES.CUSTOMS},
    },
}
