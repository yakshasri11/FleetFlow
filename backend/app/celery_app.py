from celery import Celery

from app.config import settings

celery_app = Celery(
    "fleetflow",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.beat_schedule = {
    "maintenance-reminders-daily": {
        "task": "app.tasks.send_maintenance_reminders",
        "schedule": 86400.0,  # once a day
    },
}
celery_app.conf.timezone = "UTC"
