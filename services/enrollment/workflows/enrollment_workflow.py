import uuid
from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EnrollmentWorkflowInput:
    student_id: str
    course_id: str
    student_email: str


# ── Activities ────────────────────────────────────────────────────────────────

@activity.defn
async def validate_enrollment_activity(student_id: str, course_id: str) -> None:
    """Calls course-service to verify the course exists and is published."""
    import httpx
    from config import settings

    url = f"{settings.COURSE_SERVICE_URL}/courses/{course_id}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=10.0)
        except httpx.RequestError as exc:
            raise ApplicationError(f"Course service unreachable: {exc}", non_retryable=False) from exc

    if resp.status_code == 404:
        raise ApplicationError(f"Course {course_id} not found", non_retryable=True)
    if resp.status_code != 200:
        raise ApplicationError(f"Course service error: {resp.status_code}", non_retryable=False)

    data = resp.json()
    if data.get("status") != "published":
        raise ApplicationError(
            f"Course is not published (status: {data.get('status')})", non_retryable=True
        )
    logger.info("enrollment validation passed", student_id=student_id, course_id=course_id)


@activity.defn
async def create_enrollment_activity(student_id: str, course_id: str) -> dict:
    """
    Idempotent upsert: inserts enrollment row or returns the existing one.
    Returns {"enrollment_id": str, "enrolled_at": str}.
    """
    from sqlalchemy.dialects.postgresql import insert
    from sqlalchemy import select
    from database import AsyncSessionLocal
    from models.enrollment import Enrollment, EnrollmentStatus

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
            .on_conflict_do_nothing(constraint="uq_enrollments_student_course")
            .returning(Enrollment.id, Enrollment.enrolled_at)
        )
        result = await db.execute(stmt)
        row = result.first()

        if row is None:
            existing = await db.execute(
                select(Enrollment.id, Enrollment.enrolled_at).where(
                    Enrollment.student_id == student_uuid,
                    Enrollment.course_id == course_uuid,
                )
            )
            row = existing.first()
            await db.rollback()
        else:
            await db.commit()

    enrollment_id = str(row[0])
    enrolled_at = row[1].isoformat()
    logger.info("enrollment created/found", enrollment_id=enrollment_id)
    return {"enrollment_id": enrollment_id, "enrolled_at": enrolled_at}


@activity.defn
async def send_enrollment_email_activity(student_email: str, course_id: str) -> str:
    """Welcome email dispatch — stub for Chunk 24, wired to notification-service in Chunk 25."""
    logger.info("welcome email stub", student_email=student_email, course_id=course_id)
    return f"email queued for {student_email}"


@activity.defn
async def emit_enrollment_created_event_activity(
    enrollment_id: str,
    student_id: str,
    course_id: str,
    enrolled_at: str,
) -> None:
    from events.producer import get_producer
    get_producer().emit_enrollment_created(
        enrollment_id=enrollment_id,
        student_id=student_id,
        course_id=course_id,
        enrolled_at=enrolled_at,
    )
    logger.info("enrollment.created emitted", enrollment_id=enrollment_id)


@activity.defn
async def cancel_enrollment_activity(enrollment_id: str) -> None:
    """
    Compensation: deletes the enrollment row so the student can re-enroll after fixing
    the root cause. Only runs when a post-commit activity fails permanently.
    """
    from sqlalchemy import delete
    from database import AsyncSessionLocal
    from models.enrollment import Enrollment

    async with AsyncSessionLocal() as db:
        await db.execute(
            delete(Enrollment).where(Enrollment.id == uuid.UUID(enrollment_id))
        )
        await db.commit()
    logger.info("enrollment cancelled (compensation)", enrollment_id=enrollment_id)


@activity.defn
async def emit_enrollment_cancelled_event_activity(
    enrollment_id: str,
    student_id: str,
    course_id: str,
) -> None:
    """Emits a cancellation tombstone so downstream consumers can react."""
    from kafka import KafkaProducer
    import json
    from config import settings

    producer = KafkaProducer(
        bootstrap_servers=settings.KAFKA_BROKERS.split(","),
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    producer.send(
        "enrollment.cancelled",
        key=enrollment_id.encode(),
        value={"enrollment_id": enrollment_id, "student_id": student_id, "course_id": course_id},
    )
    producer.flush()
    logger.info("enrollment.cancelled emitted", enrollment_id=enrollment_id)


# ── Workflow ──────────────────────────────────────────────────────────────────

@workflow.defn
class EnrollmentWorkflow:
    @workflow.run
    async def run(self, input: EnrollmentWorkflowInput) -> dict:
        """
        Saga: validate → create → email → emit event.
        If any step after create fails permanently, cancel_enrollment runs as compensation.
        """
        await workflow.execute_activity(
            validate_enrollment_activity,
            args=[input.student_id, input.course_id],
            start_to_close_timeout=timedelta(seconds=10),
        )

        result = await workflow.execute_activity(
            create_enrollment_activity,
            args=[input.student_id, input.course_id],
            start_to_close_timeout=timedelta(seconds=10),
        )
        enrollment_id: str = result["enrollment_id"]
        enrolled_at: str = result["enrolled_at"]

        try:
            await workflow.execute_activity(
                send_enrollment_email_activity,
                args=[input.student_email, input.course_id],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    backoff_coefficient=2.0,
                    maximum_attempts=3,
                ),
            )

            await workflow.execute_activity(
                emit_enrollment_created_event_activity,
                args=[enrollment_id, input.student_id, input.course_id, enrolled_at],
                start_to_close_timeout=timedelta(seconds=20),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    backoff_coefficient=2.0,
                    maximum_attempts=5,
                ),
            )

        except Exception:
            await workflow.execute_activity(
                cancel_enrollment_activity,
                args=[enrollment_id],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            await workflow.execute_activity(
                emit_enrollment_cancelled_event_activity,
                args=[enrollment_id, input.student_id, input.course_id],
                start_to_close_timeout=timedelta(seconds=20),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            raise

        return {
            "enrollment_id": enrollment_id,
            "student_id": input.student_id,
            "course_id": input.course_id,
            "status": "enrolled",
        }
