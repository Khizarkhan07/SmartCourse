from celery_app import celery_app
from core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(name="email.send_welcome", bind=True, max_retries=3, default_retry_delay=30)
def send_welcome_email_task(self, email: str, course_title: str) -> str:
    try:
        logger.info(
            "sending welcome email",
            task_id=self.request.id,
            email=email,
            course_title=course_title,
        )
        # TODO: replace with real email provider (SendGrid, SES, etc.)
        message = f"Welcome email sent to {email} for course '{course_title}'"
        logger.info("welcome email sent", task_id=self.request.id, email=email)
        return message
    except Exception as exc:
        logger.error("welcome email failed", task_id=self.request.id, error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(name="email.send_completion", bind=True, max_retries=3, default_retry_delay=30)
def send_completion_email_task(self, email: str, course_title: str) -> str:
    try:
        logger.info(
            "sending completion email",
            task_id=self.request.id,
            email=email,
            course_title=course_title,
        )
        # TODO: replace with real email provider
        message = f"Completion email sent to {email} for course '{course_title}'"
        logger.info("completion email sent", task_id=self.request.id, email=email)
        return message
    except Exception as exc:
        logger.error("completion email failed", task_id=self.request.id, error=str(exc))
        raise self.retry(exc=exc)
