import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from config import settings
from core.logging import configure_logging, get_logger
from core.tracing import configure_tracing
from workflows.publish_course_workflow import (
    ArchiveCourseWorkflow,
    PublishCourseWorkflow,
    emit_course_published_event_activity,
    notify_course_archived_activity,
    notify_enrolled_students_activity,
    transition_course_status_activity,
    validate_archive_activity,
    validate_publish_activity,
)

configure_logging()
configure_tracing()

logger = get_logger(__name__)


async def main() -> None:
    client = await Client.connect(settings.TEMPORAL_HOST)

    logger.info(
        "course temporal worker connected",
        temporal_host=settings.TEMPORAL_HOST,
        task_queue=settings.COURSE_TASK_QUEUE,
    )

    async with Worker(
        client,
        task_queue=settings.COURSE_TASK_QUEUE,
        workflows=[PublishCourseWorkflow, ArchiveCourseWorkflow],
        activities=[
            validate_publish_activity,
            validate_archive_activity,
            transition_course_status_activity,
            notify_enrolled_students_activity,
            notify_course_archived_activity,
            emit_course_published_event_activity,
        ],
    ):
        logger.info("course temporal worker waiting for tasks")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
