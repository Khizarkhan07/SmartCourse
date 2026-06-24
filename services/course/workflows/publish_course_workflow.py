import uuid
from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

from core.logging import get_logger
from workflows.dependencies import ApplicationError, func, select

logger = get_logger(__name__)

VALID_TRANSITIONS_PUBLISH = {"draft": ["published"]}
VALID_TRANSITIONS_ARCHIVE = {"published": ["archived"]}


@dataclass
class PublishCourseWorkflowInput:
    course_id: str
    instructor_id: str


@dataclass
class ArchiveCourseWorkflowInput:
    course_id: str
    instructor_id: str


# ─── ACTIVITIES ──────────────────────────────────────────────────────────────

@activity.defn
async def validate_publish_activity(course_id: str, instructor_id: str) -> str:
    from database import AsyncSessionLocal
    from models.course import Course, CourseStatus
    from models.lesson import Lesson
    from models.module import Module

    async with AsyncSessionLocal() as db:
        course = await db.get(Course, uuid.UUID(course_id))

        if not course:
            raise ApplicationError(f"Course {course_id} not found", non_retryable=True)

        if course.instructor_id != uuid.UUID(instructor_id):
            raise ApplicationError("You can only publish your own courses", non_retryable=True)

        if course.status != CourseStatus.draft:
            raise ApplicationError(
                f"Cannot publish a course with status '{course.status.value}'. "
                "Only draft courses can be published",
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
                "Course must have at least one lesson before publishing", non_retryable=True
            )

        course_title = course.title

    logger.info("publish validation passed", course_id=course_id)
    return course_title


@activity.defn
async def validate_archive_activity(course_id: str, instructor_id: str) -> str:
    from database import AsyncSessionLocal
    from models.course import Course, CourseStatus

    async with AsyncSessionLocal() as db:
        course = await db.get(Course, uuid.UUID(course_id))

        if not course:
            raise ApplicationError(f"Course {course_id} not found", non_retryable=True)

        if course.instructor_id != uuid.UUID(instructor_id):
            raise ApplicationError("You can only archive your own courses", non_retryable=True)

        if course.status != CourseStatus.published:
            raise ApplicationError(
                f"Cannot archive a course with status '{course.status.value}'. "
                "Only published courses can be archived",
                non_retryable=True,
            )

        course_title = course.title

    logger.info("archive validation passed", course_id=course_id)
    return course_title


@activity.defn
async def transition_course_status_activity(course_id: str, new_status: str) -> None:
    from database import AsyncSessionLocal
    from models.course import Course, CourseStatus

    async with AsyncSessionLocal() as db:
        course = await db.get(Course, uuid.UUID(course_id))
        course.status = CourseStatus(new_status)
        await db.commit()

    logger.info("course status transitioned", course_id=course_id, new_status=new_status)


@activity.defn
async def notify_enrolled_students_activity(course_id: str, course_title: str) -> str:
    # Enrollment data lives in the monolith (not yet extracted to enrollment-service).
    # Notification will be driven by the course.published Kafka event once
    # enrollment-service is extracted in Chunk 20-25.
    logger.info(
        "notify_enrolled_students stub",
        course_id=course_id,
        course_title=course_title,
        note="real notification dispatched via course.published Kafka event",
    )
    return f"Notification deferred to Kafka consumers for course '{course_title}'"


@activity.defn
async def notify_course_archived_activity(course_id: str, course_title: str) -> str:
    logger.info(
        "notify_course_archived stub",
        course_id=course_id,
        course_title=course_title,
        note="real notification dispatched via Kafka event once enrollment-service is extracted",
    )
    return f"Archive notification deferred to Kafka consumers for course '{course_title}'"


@activity.defn
async def emit_course_published_event_activity(
    course_id: str,
    instructor_id: str,
    course_title: str,
) -> None:
    from events.producer import get_producer

    producer = get_producer()
    producer.emit_course_published(
        course_id=course_id,
        instructor_id=instructor_id,
        title=course_title,
    )
    logger.info("course.published event emitted", course_id=course_id)


# ─── WORKFLOWS ───────────────────────────────────────────────────────────────

@workflow.defn
class PublishCourseWorkflow:
    @workflow.run
    async def run(self, input: PublishCourseWorkflowInput) -> dict:
        course_title = await workflow.execute_activity(
            validate_publish_activity,
            args=[input.course_id, input.instructor_id],
            start_to_close_timeout=timedelta(seconds=10),
        )

        await workflow.execute_activity(
            transition_course_status_activity,
            args=[input.course_id, "published"],
            start_to_close_timeout=timedelta(seconds=10),
        )

        notification_result = await workflow.execute_activity(
            notify_enrolled_students_activity,
            args=[input.course_id, course_title],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=2),
                backoff_coefficient=2.0,
                maximum_attempts=3,
            ),
        )

        await workflow.execute_activity(
            emit_course_published_event_activity,
            args=[input.course_id, input.instructor_id, course_title],
            start_to_close_timeout=timedelta(seconds=20),
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
