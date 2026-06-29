import asyncio

from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from temporalio.client import Client
from temporalio.worker import Worker

from config import settings
from core.logging import configure_logging
from core.tracing import configure_tracing
from workflows.course_completion_workflow import (
    CourseCompletionWorkflow,
    emit_enrollment_completed_event_activity,
    fetch_course_title_activity,
    fetch_student_details_activity,
)
from workflows.enrollment_workflow import (
    EnrollmentWorkflow,
    cancel_enrollment_activity,
    create_enrollment_activity,
    emit_enrollment_cancelled_event_activity,
    emit_enrollment_created_event_activity,
    send_enrollment_email_activity,
    validate_enrollment_activity,
)


async def main() -> None:
    configure_logging()
    configure_tracing()
    HTTPXClientInstrumentor().instrument()

    client = await Client.connect(settings.TEMPORAL_HOST)
    async with Worker(
        client,
        task_queue=settings.ENROLLMENT_TASK_QUEUE,
        workflows=[EnrollmentWorkflow, CourseCompletionWorkflow],
        activities=[
            validate_enrollment_activity,
            create_enrollment_activity,
            send_enrollment_email_activity,
            emit_enrollment_created_event_activity,
            cancel_enrollment_activity,
            emit_enrollment_cancelled_event_activity,
            fetch_student_details_activity,
            fetch_course_title_activity,
            emit_enrollment_completed_event_activity,
        ],
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
