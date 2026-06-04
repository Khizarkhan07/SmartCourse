"""

Run this with:
    python -m app.temporal_worker

Keep it running alongside FastAPI.
"""

import asyncio
from contextlib import AsyncExitStack
from temporalio.client import Client
from temporalio.worker import Worker

from app.workflows.hello_workflow import HelloWorldWorkflow, say_hello, send_welcome_email
from app.workflows.enrollment_workflow import (
    EnrollmentWorkflow,
    validate_enrollment_activity,
    create_enrollment_activity,
    send_enrollment_email_activity,
)
from app.workflows.publish_course_workflow import (
    ArchiveCourseWorkflow,
    notify_course_archived_activity,
    validate_archive_activity,
    PublishCourseWorkflow,
    validate_publish_activity,
    transition_course_status_activity,
    notify_enrolled_students_activity,
)
from app.temporal_client import (
    COURSE_TASK_QUEUE,
    ENROLLMENT_TASK_QUEUE,
    NOTIFICATION_TASK_QUEUE,
)


async def main():
    # Connect to the Temporal server
    client = await Client.connect("localhost:7233")

    print(f"✅ Connected to Temporal server")
    print(f"📋 Queue (workflows/enrollment): '{ENROLLMENT_TASK_QUEUE}'")
    print(f"📋 Queue (course state): '{COURSE_TASK_QUEUE}'")
    print(f"📋 Queue (notifications): '{NOTIFICATION_TASK_QUEUE}'")
    print(f"🔄 Enrollment queue workflows: HelloWorldWorkflow, EnrollmentWorkflow")
    print(f"🔄 Course queue workflows: PublishCourseWorkflow, ArchiveCourseWorkflow")
    print(f"⚡ Enrollment queue activities: say_hello, validate_enrollment, create_enrollment")
    print(f"⚡ Course queue activities: validate_publish, transition_course_status, validate_archive")
    print(f"⚡ Notification queue activities: send_welcome_email, send_enrollment_email,")
    print(f"                               notify_enrolled_students, notify_course_archived")
    print(f"\nWaiting for tasks... (Ctrl+C to stop)\n")

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(
            Worker(
                client,
                task_queue=ENROLLMENT_TASK_QUEUE,
                workflows=[HelloWorldWorkflow, EnrollmentWorkflow],
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
                    notify_enrolled_students_activity,
                    notify_course_archived_activity,
                ],
            )
        )

        await asyncio.Future()  # run forever until Ctrl+C


if __name__ == "__main__":
    asyncio.run(main())
