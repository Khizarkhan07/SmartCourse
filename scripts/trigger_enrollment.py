
import asyncio
from temporalio.client import Client
from app.workflows.enrollment_workflow import EnrollmentWorkflow, EnrollmentWorkflowInput
from app.infrastructure.temporal import ENROLLMENT_TASK_QUEUE

TASK_QUEUE = ENROLLMENT_TASK_QUEUE

# ── FILL THESE IN ──────────────────────────────────────────────────
STUDENT_ID    = "2a8f1630-97bc-4afb-b1b0-b8c963b26dcc"
COURSE_ID     = "b366da3c-4bcc-4da3-bc0a-a28e5b899a59"
STUDENT_EMAIL = "khizar@gmail.com"
# ───────────────────────────────────────────────────────────────────


async def main():
    client = await Client.connect("localhost:7233")

    print("🚀 Starting EnrollmentWorkflow...\n")

    result = await client.execute_workflow(
        EnrollmentWorkflow.run,
        EnrollmentWorkflowInput(
            student_id=STUDENT_ID,
            course_id=COURSE_ID,
            student_email=STUDENT_EMAIL,
        ),
        id=f"enroll-{STUDENT_ID}-{COURSE_ID}",
        task_queue=TASK_QUEUE,
    )

    print(f"✅ Workflow completed!")
    print(f"📨 Result: {result}")
    print(f"\nCheck the Web UI: http://localhost:8233")


if __name__ == "__main__":
    asyncio.run(main())
