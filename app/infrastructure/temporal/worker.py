"""Temporal worker setup and task queue registration.

Run this module alongside FastAPI with:
    python -m app.infrastructure.temporal.worker

This keeps the worker listening for tasks from all three queues:
- ENROLLMENT_TASK_QUEUE: Enrollment workflows and validation
- COURSE_TASK_QUEUE: Course publishing and archival
- NOTIFICATION_TASK_QUEUE: Async email and notification activities
"""

import asyncio
from contextlib import AsyncExitStack
from temporalio.client import Client
from temporalio.worker import Worker

from app.config import settings
from app.core.logging import configure_logging, get_logger
from app.workflows.hello_workflow import HelloWorldWorkflow, say_hello, send_welcome_email
from app.workflows.enrollment_workflow import (
    EnrollmentWorkflow,
    validate_enrollment_activity,
    create_enrollment_activity,
    emit_enrollment_created_event_activity,
    send_enrollment_email_activity,
)
from app.workflows.publish_course_workflow import (
    ArchiveCourseWorkflow,
    emit_course_published_event_activity,
    notify_course_archived_activity,
    validate_archive_activity,
    PublishCourseWorkflow,
    validate_publish_activity,
    transition_course_status_activity,
    notify_enrolled_students_activity,
)
from app.workflows.course_completion_workflow import (
    CourseCompletionWorkflow,
    send_course_completion_email_activity,
)
from app.infrastructure.temporal.client import (
    COURSE_TASK_QUEUE,
    ENROLLMENT_TASK_QUEUE,
    NOTIFICATION_TASK_QUEUE,
)


logger = get_logger(__name__)


async def main():
    configure_logging()

    # Connect to the Temporal server
    client = await Client.connect(settings.TEMPORAL_HOST)

    logger.info(
        "temporal worker connected",
        temporal_host=settings.TEMPORAL_HOST,
        enrollment_task_queue=ENROLLMENT_TASK_QUEUE,
        course_task_queue=COURSE_TASK_QUEUE,
        notification_task_queue=NOTIFICATION_TASK_QUEUE,
        enrollment_workflows=[
            "HelloWorldWorkflow",
            "EnrollmentWorkflow",
            "CourseCompletionWorkflow",
        ],
        course_workflows=["PublishCourseWorkflow", "ArchiveCourseWorkflow"],
        enrollment_activities=[
            "say_hello",
            "validate_enrollment_activity",
            "create_enrollment_activity",
        ],
        course_activities=[
            "validate_publish_activity",
            "transition_course_status_activity",
            "validate_archive_activity",
        ],
        notification_activities=[
            "send_welcome_email",
            "send_enrollment_email_activity",
            "emit_enrollment_created_event_activity",
            "notify_enrolled_students_activity",
            "notify_course_archived_activity",
            "emit_course_published_event_activity",
            "send_course_completion_email_activity",
        ],
    )
    logger.info("temporal worker waiting for tasks")

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(
            Worker(
                client,
                task_queue=ENROLLMENT_TASK_QUEUE,
                workflows=[HelloWorldWorkflow, EnrollmentWorkflow, CourseCompletionWorkflow],
                activities=[
                    say_hello,
                    validate_enrollment_activity,
                    create_enrollment_activity,
                ],
            )
        )

        await stack.enter_async_context(
            Worker(
                client,
                task_queue=COURSE_TASK_QUEUE,
                workflows=[PublishCourseWorkflow, ArchiveCourseWorkflow],
                activities=[
                    validate_publish_activity,
                    transition_course_status_activity,
                    validate_archive_activity,
                ],
            )
        )

        await stack.enter_async_context(
            Worker(
                client,
                task_queue=NOTIFICATION_TASK_QUEUE,
                activities=[
                    send_welcome_email,
                    send_enrollment_email_activity,
                    emit_enrollment_created_event_activity,
                    notify_enrolled_students_activity,
                    notify_course_archived_activity,
                    emit_course_published_event_activity,
                    send_course_completion_email_activity,
                ],
            )
        )

        await asyncio.Future()  # run forever until Ctrl+C


if __name__ == "__main__":
    asyncio.run(main())
