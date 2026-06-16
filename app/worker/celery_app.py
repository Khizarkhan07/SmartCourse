from celery import Celery

from app.config import settings

celery_app = Celery(
    "smartcourse",
    broker=settings.RABBITMQ_URL,
    backend=settings.REDIS_URL,  # stores task results in Redis
    include=[
        "app.worker.tasks.email_tasks",
        "app.worker.tasks.analytics_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # tasks expire from result backend after 1 hour
    result_expires=3600,
)
