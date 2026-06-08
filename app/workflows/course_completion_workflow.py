from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

from app.temporal_client import NOTIFICATION_TASK_QUEUE


@dataclass
class CourseCompletionWorkflowInput:
    enrollment_id: str
    student_id: str
    student_email: str
    course_id: str
    course_title: str


@activity.defn
async def send_course_completion_email_activity(
    student_email: str,
    course_title: str,
) -> str:
    # TODO: replace with real certificate generation + email provider.
    message = f"Course completion email sent to {student_email} for '{course_title}'"
    print(f"[Activity] 🎓 {message}")
    return message


@workflow.defn
class CourseCompletionWorkflow:
    @workflow.run
    async def run(self, input: CourseCompletionWorkflowInput) -> dict:
        notification_result = await workflow.execute_activity(
            send_course_completion_email_activity,
            args=[input.student_email, input.course_title],
            start_to_close_timeout=timedelta(seconds=30),
            task_queue=NOTIFICATION_TASK_QUEUE,
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=2),
                backoff_coefficient=2.0,
                maximum_attempts=3,
            ),
        )

        return {
            "enrollment_id": input.enrollment_id,
            "student_id": input.student_id,
            "course_id": input.course_id,
            "status": "completed",
            "notification": notification_result,
        }
