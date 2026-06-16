
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from app.core.logging import get_logger
from app.infrastructure.temporal import NOTIFICATION_TASK_QUEUE
from app.workflows.dependencies import (
    ApplicationError,
    insert,
    select,
)


logger = get_logger(__name__)


@dataclass
class EnrollmentWorkflowInput:
    student_id: str      # UUID as string (dataclasses serialize cleanly)
    course_id: str       # UUID as string
    student_email: str   # needed for the welcome email activity


# ACTIVITIES


@activity.defn
async def validate_enrollment_activity(student_id: str, course_id: str) -> None:
    from app.infrastructure.database import AsyncSessionLocal
    from app.models import Course, CourseStatus

    async with AsyncSessionLocal() as db:
        # Check course exists and is published
        course = await db.get(Course, uuid.UUID(course_id))
        if not course:
            raise ApplicationError(f"Course {course_id} not found", non_retryable=True)
        if course.status != CourseStatus.published:
            raise ApplicationError(
                f"Course '{course.title}' is not published", non_retryable=True
            )

    logger.info(
        "enrollment validation passed",
        activity="validate_enrollment_activity",
        student_id=student_id,
        course_id=course_id,
    )


@activity.defn
async def create_enrollment_activity(student_id: str, course_id: str) -> str:
    """
    Idempotent DB write — returns existing enrollment ID if already enrolled,
    creates a new row otherwise.

    This is the idempotency guarantee: calling this twice with the same
    student+course always returns the same enrollment_id.
    """
    from app.core.metrics import activity_duration_seconds, push_metrics  # deferred — urllib blocked in sandbox
    from app.infrastructure.database import AsyncSessionLocal
    from app.models import Enrollment, EnrollmentStatus

    _t0 = time.monotonic()
    try:
        student_uuid = uuid.UUID(student_id)
        course_uuid = uuid.UUID(course_id)

        async with AsyncSessionLocal() as db:
            stmt = (
                insert(Enrollment)
                .values(
                    student_id=student_uuid,
                    course_id=course_uuid,
                    status=EnrollmentStatus.enrolled,
                    progress_percentage=0,
                )
                .on_conflict_do_nothing(
                    index_elements=[Enrollment.student_id, Enrollment.course_id]
                )
                .returning(Enrollment.id)
            )

            insert_result = await db.execute(stmt)
            enrollment_id = insert_result.scalar_one_or_none()

            if enrollment_id is None:
                existing_result = await db.execute(
                    select(Enrollment.id).where(
                        (Enrollment.student_id == student_uuid)
                        & (Enrollment.course_id == course_uuid)
                    )
                )
                enrollment_id = existing_result.scalar_one()
                await db.rollback()
                logger.info(
                    "enrollment already exists",
                    activity="create_enrollment_activity",
                    student_id=student_id,
                    course_id=course_id,
                    enrollment_id=str(enrollment_id),
                )
                return str(enrollment_id)

            await db.commit()
        logger.info(
            "enrollment created",
            activity="create_enrollment_activity",
            student_id=student_id,
            course_id=course_id,
            enrollment_id=str(enrollment_id),
        )
        return str(enrollment_id)
    finally:
        activity_duration_seconds.labels(activity="create_enrollment_activity").observe(
            time.monotonic() - _t0
        )
        await push_metrics()


@activity.defn
async def send_enrollment_email_activity(email: str, course_title: str) -> str:
    """
    Sends a welcome email to the student.

    In production this would call SendGrid, SES, etc.
    Currently mocked — just logs and returns.

    This activity has a RetryPolicy configured in the workflow,
    so transient failures (email server down) are retried automatically.
    """
    from app.core.metrics import activity_duration_seconds, push_metrics  # deferred — urllib blocked in sandbox
    from app.worker.tasks.email_tasks import send_welcome_email_task  # deferred — celery import safe outside sandbox

    _t0 = time.monotonic()
    try:
        # Dispatch to Celery — fire-and-forget, Celery handles retries independently
        send_welcome_email_task.delay(email, course_title)
        logger.info(
            "welcome email task dispatched",
            activity="send_enrollment_email_activity",
            email=email,
            course_title=course_title,
        )
        return f"Welcome email queued for {email}"
    finally:
        activity_duration_seconds.labels(activity="send_enrollment_email_activity").observe(
            time.monotonic() - _t0
        )
        await push_metrics()


@activity.defn
async def emit_enrollment_created_event_activity(
    enrollment_id: str,
    student_id: str,
    course_id: str,
) -> None:
    from app.core.metrics import activity_duration_seconds, push_metrics  # deferred — urllib blocked in sandbox
    from app.events import KafkaEventProducer

    _t0 = time.monotonic()
    try:
        producer = KafkaEventProducer()
        producer.emit_enrollment_created(
            enrollment_id=enrollment_id,
            student_id=student_id,
            course_id=course_id,
            status="enrolled",
            progress_percentage=0,
        )

        logger.info(
            "enrollment.created event emitted",
            activity="emit_enrollment_created_event_activity",
            enrollment_id=enrollment_id,
            student_id=student_id,
            course_id=course_id,
        )
    finally:
        activity_duration_seconds.labels(activity="emit_enrollment_created_event_activity").observe(
            time.monotonic() - _t0
        )
        await push_metrics()



@workflow.defn
class EnrollmentWorkflow:
    @workflow.run
    async def run(self, input: EnrollmentWorkflowInput) -> dict:
        """
        Orchestrates enrollment in 3 steps.

        If any step fails permanently (non-retryable error), the whole
        workflow fails and nothing further is executed — no partial state.
        """

        # Step 1: Validate (fast, no side effects — fail early if invalid)
        await workflow.execute_activity(
            validate_enrollment_activity,
            args=[input.student_id, input.course_id],
            start_to_close_timeout=timedelta(seconds=10),
        )

        # Step 2: Write enrollment to DB
        # Only runs if validation passed — avoids dirty writes
        enrollment_id = await workflow.execute_activity(
            create_enrollment_activity,
            args=[input.student_id, input.course_id],
            start_to_close_timeout=timedelta(seconds=10),
        )

        # Step 3: Send welcome email — retried up to 3 times if it fails
        # If this fails after all retries, enrollment is still created (step 2 committed).
        # In production you'd handle this with a compensation activity or a signal.
        await workflow.execute_activity(
            send_enrollment_email_activity,
            args=[input.student_email, "SmartCourse"],   # course title placeholder
            start_to_close_timeout=timedelta(seconds=30),
            task_queue=NOTIFICATION_TASK_QUEUE,
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=2),
                backoff_coefficient=2.0,
                maximum_attempts=3,
            ),
        )

        # Step 4: Emit durable domain event to Kafka for downstream consumers
        await workflow.execute_activity(
            emit_enrollment_created_event_activity,
            args=[enrollment_id, input.student_id, input.course_id],
            start_to_close_timeout=timedelta(seconds=20),
            task_queue=NOTIFICATION_TASK_QUEUE,
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=2),
                backoff_coefficient=2.0,
                maximum_attempts=3,
            ),
        )

        return {
            "enrollment_id": enrollment_id,
            "student_id": input.student_id,
            "course_id": input.course_id,
            "status": "enrolled",
        }
