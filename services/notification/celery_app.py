from celery import Celery

from config import settings

celery_app = Celery(
    "notification",
    broker=settings.RABBITMQ_URL,
    backend=settings.REDIS_URL,
    include=["tasks.email_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    task_routes={
        "email.*": {"queue": "notification"},
    },
)
