from app.core.logging import get_logger
from app.worker.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="email.send_welcome", bind=True, max_retries=3, default_retry_delay=30)
def send_welcome_email_task(self, email: str, course_title: str) -> str:
    """
    Send a welcome email to a newly enrolled student.
    Retried up to 3 times with 30s delay on failure.
    Currently mocked — replace with real provider (SendGrid, SES, etc.)
    """
    try:
        # TODO: replace with real email provider call
        logger.info(
            "sending welcome email",
            task_id=self.request.id,
            email=email,
            course_title=course_title,
        )
        message = f"Welcome email sent to {email} for course '{course_title}'"
        logger.info(
            "welcome email sent",
            task_id=self.request.id,
            email=email,
            course_title=course_title,
        )
        return message
    except Exception as exc:
        logger.error(
            "welcome email failed",
            task_id=self.request.id,
            email=email,
            error=str(exc),
        )
        raise self.retry(exc=exc)


@celery_app.task(name="email.send_completion", bind=True, max_retries=3, default_retry_delay=30)
def send_completion_email_task(self, email: str, course_title: str) -> str:
    """
    Send a course completion certificate email.
    Currently mocked — replace with real provider.
    """
    try:
        logger.info(
            "sending completion email",
            task_id=self.request.id,
            email=email,
            course_title=course_title,
        )
        message = f"Completion email sent to {email} for course '{course_title}'"
        logger.info(
            "completion email sent",
            task_id=self.request.id,
            email=email,
            course_title=course_title,
        )
        return message
    except Exception as exc:
        logger.error(
            "completion email failed",
            task_id=self.request.id,
            email=email,
            error=str(exc),
        )
        raise self.retry(exc=exc)
