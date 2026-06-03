"""

Run this with:
    python -m app.temporal_worker

Keep it running alongside FastAPI.
"""

import asyncio
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
from app.temporal_client import TASK_QUEUE  # single source of truth


async def main():
    # Connect to the Temporal server
    client = await Client.connect("localhost:7233")

    print(f"✅ Connected to Temporal server")
    print(f"📋 Listening on task queue: '{TASK_QUEUE}'")
    print(f"🔄 Registered workflows: HelloWorldWorkflow, EnrollmentWorkflow, PublishCourseWorkflow, ArchiveCourseWorkflow")
    print(f"⚡ Registered activities: say_hello, send_welcome_email,")
    print(f"                          validate_enrollment, create_enrollment, send_enrollment_email,")
    print(f"                          validate_publish, transition_course_status, notify_enrolled_students,")
    print(f"                          validate_archive, notify_course_archived")
    print(f"\nWaiting for tasks... (Ctrl+C to stop)\n")

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[
            HelloWorldWorkflow,
            EnrollmentWorkflow,
            PublishCourseWorkflow,
            ArchiveCourseWorkflow,
        ],
        activities=[
            say_hello,
            send_welcome_email,
            validate_enrollment_activity,
            create_enrollment_activity,
            send_enrollment_email_activity,
            validate_publish_activity,
            transition_course_status_activity,
            notify_enrolled_students_activity,
            validate_archive_activity,
            notify_course_archived_activity,
        ],
    ):
        await asyncio.Future()  # run forever until Ctrl+C


if __name__ == "__main__":
    asyncio.run(main())
