from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CourseCompletionWorkflowInput:
    enrollment_id: str
    student_id: str
    course_id: str
    completed_at: str  # ISO-8601


# ── Activities ────────────────────────────────────────────────────────────────

@activity.defn
async def fetch_student_details_activity(student_id: str) -> dict:
    """Calls identity-service /internal/users/{id} to get student name + email."""
    import httpx
    from config import settings

    url = f"{settings.IDENTITY_SERVICE_URL}/internal/users/{student_id}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=10.0)
        except httpx.RequestError as exc:
            from temporalio.exceptions import ApplicationError
            raise ApplicationError(f"Identity service unreachable: {exc}", non_retryable=False) from exc

    if resp.status_code == 404:
        return {"name": "", "email": ""}
    resp.raise_for_status()
    data = resp.json()
    return {"name": data.get("name", ""), "email": data.get("email", "")}


@activity.defn
async def fetch_course_title_activity(course_id: str) -> str:
    """Calls course-service GET /courses/{id} to get the course title."""
    import httpx
    from config import settings

    url = f"{settings.COURSE_SERVICE_URL}/courses/{course_id}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=10.0)
        except httpx.RequestError:
            return ""

    if resp.status_code != 200:
        return ""
    return resp.json().get("title", "")


@activity.defn
async def emit_enrollment_completed_event_activity(
    enrollment_id: str,
    student_id: str,
    student_name: str,
    course_id: str,
    course_title: str,
    completed_at: str,
) -> None:
    from events.producer import get_producer
    get_producer().emit_enrollment_completed(
        enrollment_id=enrollment_id,
        student_id=student_id,
        student_name=student_name,
        course_id=course_id,
        course_title=course_title,
        completed_at=completed_at,
    )
    logger.info("enrollment.completed emitted", enrollment_id=enrollment_id)


# ── Workflow ──────────────────────────────────────────────────────────────────

@workflow.defn
class CourseCompletionWorkflow:
    @workflow.run
    async def run(self, input: CourseCompletionWorkflowInput) -> dict:
        """
        Emits the enrollment.completed Kafka event after fetching student + course details.
        Triggers certificate-service via the event consumer.
        """
        student = await workflow.execute_activity(
            fetch_student_details_activity,
            args=[input.student_id],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        course_title = await workflow.execute_activity(
            fetch_course_title_activity,
            args=[input.course_id],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        await workflow.execute_activity(
            emit_enrollment_completed_event_activity,
            args=[
                input.enrollment_id,
                input.student_id,
                student["name"],
                input.course_id,
                course_title,
                input.completed_at,
            ],
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=2),
                backoff_coefficient=2.0,
                maximum_attempts=5,
            ),
        )

        return {
            "enrollment_id": input.enrollment_id,
            "student_id": input.student_id,
            "course_id": input.course_id,
            "status": "completed",
        }
