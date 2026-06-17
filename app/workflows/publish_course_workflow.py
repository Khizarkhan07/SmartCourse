import uuid
from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from app.core.logging import get_logger
from app.infrastructure.temporal import NOTIFICATION_TASK_QUEUE
from app.workflows.dependencies import (
    ApplicationError,
    func,
    select,
)


logger = get_logger(__name__)


@dataclass
class PublishCourseWorkflowInput:
    course_id: str       # UUID as string
    instructor_id: str   # UUID as string


@dataclass
class ArchiveCourseWorkflowInput:
    course_id: str       # UUID as string
    instructor_id: str   # UUID as string


# ACTIVITIES

@activity.defn
async def validate_publish_activity(course_id: str, instructor_id: str) -> str:
    from app.infrastructure.database import AsyncSessionLocal
    from app.models import Course, CourseStatus, Lesson, Module

    VALID_TRANSITIONS = {
        CourseStatus.draft: [CourseStatus.published],
        CourseStatus.published: [CourseStatus.archived],
        CourseStatus.archived: [],
    }

    async with AsyncSessionLocal() as db:
        course = await db.get(Course, uuid.UUID(course_id))

        if not course:
            raise ApplicationError(f"Course {course_id} not found", non_retryable=True)

        if course.instructor_id != uuid.UUID(instructor_id):
            raise ApplicationError(
                "You can only publish your own courses", non_retryable=True
            )

        if CourseStatus.published not in VALID_TRANSITIONS[course.status]:
            raise ApplicationError(
                f"Cannot publish a course with status '{course.status}'. "
                f"Only draft courses can be published",
                non_retryable=True,
            )

        if not course.description:
            raise ApplicationError(
                "Course must have a description before publishing", non_retryable=True
            )

        lesson_count_result = await db.execute(
            select(func.count(Lesson.id))
            .join(Module, Lesson.module_id == Module.id)
            .where(Module.course_id == course.id)
        )
        if lesson_count_result.scalar() == 0:
            raise ApplicationError(
                "Course must have at least one lesson before publishing",
                non_retryable=True,
            )

        course_title = course.title

    logger.info(
        "publish validation passed",
        activity="validate_publish_activity",
        course_id=course_id,
        instructor_id=instructor_id,
        course_title=course_title,
    )
    return course_title


@activity.defn
async def validate_archive_activity(course_id: str, instructor_id: str) -> str:
    from app.infrastructure.database import AsyncSessionLocal
    from app.models import Course, CourseStatus

    VALID_TRANSITIONS = {
        CourseStatus.draft: [CourseStatus.published],
        CourseStatus.published: [CourseStatus.archived],
        CourseStatus.archived: [],
    }

    async with AsyncSessionLocal() as db:
        course = await db.get(Course, uuid.UUID(course_id))

        if not course:
            raise ApplicationError(f"Course {course_id} not found", non_retryable=True)

        if course.instructor_id != uuid.UUID(instructor_id):
            raise ApplicationError(
                "You can only archive your own courses", non_retryable=True
            )

        if CourseStatus.archived not in VALID_TRANSITIONS[course.status]:
            raise ApplicationError(
                f"Cannot archive a course with status '{course.status}'. "
                f"Only published courses can be archived",
                non_retryable=True,
            )

        course_title = course.title

    logger.info(
        "archive validation passed",
        activity="validate_archive_activity",
        course_id=course_id,
        instructor_id=instructor_id,
        course_title=course_title,
    )
    return course_title


@activity.defn
async def transition_course_status_activity(course_id: str, new_status: str) -> None:
    """
    DB write — transitions the course status.

    Kept generic (accepts new_status as string) so both publish
    and archive can reuse the same activity.
    """
    from app.infrastructure.database import AsyncSessionLocal
    from app.models import Course, CourseStatus
    
    async with AsyncSessionLocal() as db:
        course = await db.get(Course, uuid.UUID(course_id))
        course.status = CourseStatus(new_status)
        await db.commit()

    logger.info(
        "course status transitioned",
        activity="transition_course_status_activity",
        course_id=course_id,
        new_status=new_status,
    )


@activity.defn
async def notify_enrolled_students_activity(course_id: str, course_title: str) -> str:
    """
    Notifies all enrolled students that a course is now published.

    In production: query enrollments for this course, send each student an email.
    Currently mocked — just logs and returns.

    Has a RetryPolicy in the workflow so transient failures are retried
    without re-running the status transition.
    """
    from app.infrastructure.database import AsyncSessionLocal
    from app.models import Enrollment, User

    async with AsyncSessionLocal() as db:
        # JOIN enrollments → users to get student emails in one query
        result = await db.execute(
            select(User.email)
            .join(Enrollment, Enrollment.student_id == User.id)
            .where(Enrollment.course_id == uuid.UUID(course_id))
        )
        student_emails = result.scalars().all()

    # TODO: replace with real email provider (SendGrid, SES, etc.)
    for email in student_emails:
        logger.info(
            "sending publish notification",
            activity="notify_enrolled_students_activity",
            course_id=course_id,
            course_title=course_title,
            email=email,
        )

    student_count = len(student_emails)
    logger.info(
        "publish notifications sent",
        activity="notify_enrolled_students_activity",
        course_id=course_id,
        course_title=course_title,
        student_count=student_count,
    )
    return f"Notified {student_count} student(s) for course '{course_title}'"


@activity.defn
async def notify_course_archived_activity(course_id: str, course_title: str) -> str:
    from app.infrastructure.database import AsyncSessionLocal
    from app.models import Enrollment, User
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User.email)
            .join(Enrollment, Enrollment.student_id == User.id)
            .where(Enrollment.course_id == uuid.UUID(course_id))
        )
        student_emails = result.scalars().all()

    for email in student_emails:
        logger.info(
            "sending archive notification",
            activity="notify_course_archived_activity",
            course_id=course_id,
            course_title=course_title,
            email=email,
        )

    student_count = len(student_emails)
    logger.info(
        "archive notifications sent",
        activity="notify_course_archived_activity",
        course_id=course_id,
        course_title=course_title,
        student_count=student_count,
    )
    return f"Archive notification sent to {student_count} student(s) for course '{course_title}'"


@activity.defn
async def emit_course_published_event_activity(
    course_id: str,
    instructor_id: str,
    course_title: str,
) -> None:
    from opentelemetry import trace  # deferred — module must be imported after configure_tracing()
    from app.events import KafkaEventProducer

    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span(
        "emit_course_published_event_activity",
        kind=trace.SpanKind.PRODUCER,
    ) as span:
        span.set_attribute("course.id", course_id)
        span.set_attribute("course.title", course_title)
        span.set_attribute("instructor.id", instructor_id)
        producer = KafkaEventProducer()
        producer.emit_course_published(
            course_id=course_id,
            instructor_id=instructor_id,
            title=course_title,
        )
        logger.info(
            "course.published event emitted",
            activity="emit_course_published_event_activity",
            course_id=course_id,
            instructor_id=instructor_id,
            course_title=course_title,
        )


# ─────────────────────────────────────────────────────────
# WORKFLOW
# ─────────────────────────────────────────────────────────

@workflow.defn
class PublishCourseWorkflow:
    @workflow.run
    async def run(self, input: PublishCourseWorkflowInput) -> dict:
        """
        Publishes a course in 3 durable steps.

        If validation fails → whole workflow fails immediately (non_retryable).
        If status transition fails → retried (transient DB issue).
        If notification fails → retried independently, course stays published.
        """

        # Step 1: Validate everything before touching the DB
        course_title = await workflow.execute_activity(
            validate_publish_activity,
            args=[input.course_id, input.instructor_id],
            start_to_close_timeout=timedelta(seconds=10),
        )

        # Step 2: Transition status — retried automatically on DB blip
        await workflow.execute_activity(
            transition_course_status_activity,
            args=[input.course_id, "published"],
            start_to_close_timeout=timedelta(seconds=10),
        )

        # Step 3: Notify students — retried independently if email service is down
        # Course is already published at this point; only this step retries on failure
        notification_result = await workflow.execute_activity(
            notify_enrolled_students_activity,
            args=[input.course_id, course_title],
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
            emit_course_published_event_activity,
            args=[input.course_id, input.instructor_id, course_title],
            start_to_close_timeout=timedelta(seconds=20),
            task_queue=NOTIFICATION_TASK_QUEUE,
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=2),
                backoff_coefficient=2.0,
                maximum_attempts=3,
            ),
        )

        return {
            "course_id": input.course_id,
            "status": "published",
            "course_title": course_title,
            "notification": notification_result,
        }


@workflow.defn
class ArchiveCourseWorkflow:
    @workflow.run
    async def run(self, input: ArchiveCourseWorkflowInput) -> dict:
        course_title = await workflow.execute_activity(
            validate_archive_activity,
            args=[input.course_id, input.instructor_id],
            start_to_close_timeout=timedelta(seconds=10),
        )

        await workflow.execute_activity(
            transition_course_status_activity,
            args=[input.course_id, "archived"],
            start_to_close_timeout=timedelta(seconds=10),
        )

        notification_result = await workflow.execute_activity(
            notify_course_archived_activity,
            args=[input.course_id, course_title],
            start_to_close_timeout=timedelta(seconds=30),
            task_queue=NOTIFICATION_TASK_QUEUE,
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=2),
                backoff_coefficient=2.0,
                maximum_attempts=3,
            ),
        )

        return {
            "course_id": input.course_id,
            "status": "archived",
            "course_title": course_title,
            "notification": notification_result,
        }
