
import asyncio
from contextlib import AsyncExitStack
from temporalio.client import Client
from temporalio.worker import Worker

from app.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.tracing import configure_tracing
from app.workflows.enrollment_workflow import (
    EnrollmentWorkflow,
    validate_enrollment_activity,
    create_enrollment_activity,
    emit_enrollment_created_event_activity,
    send_enrollment_email_activity,
)
from app.workflows.course_completion_workflow import (
    CourseCompletionWorkflow,
    send_course_completion_email_activity,
    emit_enrollment_completed_event_activity,
)
from app.infrastructure.temporal.client import (
    ENROLLMENT_TASK_QUEUE,
    NOTIFICATION_TASK_QUEUE,
)


logger = get_logger(__name__)


async def main():
    configure_logging()
    configure_tracing()

    client = await Client.connect(settings.TEMPORAL_HOST)

    logger.info(
        "temporal worker connected",
        temporal_host=settings.TEMPORAL_HOST,
        enrollment_task_queue=ENROLLMENT_TASK_QUEUE,
        notification_task_queue=NOTIFICATION_TASK_QUEUE,
        enrollment_workflows=["EnrollmentWorkflow", "CourseCompletionWorkflow"],
        enrollment_activities=["validate_enrollment_activity", "create_enrollment_activity"],
        notification_activities=[
            "send_enrollment_email_activity",
            "emit_enrollment_created_event_activity",
            "send_course_completion_email_activity",
            "emit_enrollment_completed_event_activity",
        ],
    )
    logger.info("temporal worker waiting for tasks")

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(
            Worker(
                client,
                task_queue=ENROLLMENT_TASK_QUEUE,
                workflows=[EnrollmentWorkflow, CourseCompletionWorkflow],
                activities=[
                    validate_enrollment_activity,
                    create_enrollment_activity,
                ],
            )
        )

        await stack.enter_async_context(
            Worker(
                client,
                task_queue=NOTIFICATION_TASK_QUEUE,
                activities=[
                    send_enrollment_email_activity,
                    emit_enrollment_created_event_activity,
                    send_course_completion_email_activity,
                    emit_enrollment_completed_event_activity,
                ],
            )
        )

        await asyncio.Future()  # run forever until Ctrl+C


if __name__ == "__main__":
    asyncio.run(main())
