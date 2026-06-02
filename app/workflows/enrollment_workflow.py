
import uuid
from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy



@dataclass
class EnrollmentWorkflowInput:
    student_id: str      # UUID as string (dataclasses serialize cleanly)
    course_id: str       # UUID as string
    student_email: str   # needed for the welcome email activity


# ACTIVITIES


@activity.defn
async def validate_enrollment_activity(student_id: str, course_id: str) -> None:
   
    from sqlalchemy import select
    from temporalio.exceptions import ApplicationError

    from app.database import AsyncSessionLocal
    from app.models import Course, CourseStatus, Enrollment

    async with AsyncSessionLocal() as db:
        # Check course exists and is published
        course = await db.get(Course, uuid.UUID(course_id))
        if not course:
            raise ApplicationError(f"Course {course_id} not found", non_retryable=True)
        if course.status != CourseStatus.published:
            raise ApplicationError(
                f"Course '{course.title}' is not published", non_retryable=True
            )

        # Check for duplicate enrollment
        existing = await db.execute(
            select(Enrollment).where(
                (Enrollment.student_id == uuid.UUID(student_id))
                & (Enrollment.course_id == uuid.UUID(course_id))
            )
        )
        if existing.scalar_one_or_none():
            raise ApplicationError(
                f"Student {student_id} is already enrolled in course {course_id}",
                non_retryable=True,
            )

    print(f"[Activity] ✅ Validation passed for student {student_id} → course {course_id}")


@activity.defn
async def create_enrollment_activity(student_id: str, course_id: str) -> str:
    """
    DB write — creates the enrollment row and returns the new enrollment ID.

    Returns the UUID string of the created enrollment so the workflow
    can include it in its final result.
    """
    from app.database import AsyncSessionLocal
    from app.models import Enrollment

    async with AsyncSessionLocal() as db:
        enrollment = Enrollment(
            student_id=uuid.UUID(student_id),
            course_id=uuid.UUID(course_id),
        )
        db.add(enrollment)
        await db.commit()
        await db.refresh(enrollment)

    enrollment_id = str(enrollment.id)
    print(f"[Activity] ✅ Enrollment created: {enrollment_id}")
    return enrollment_id


@activity.defn
async def send_enrollment_email_activity(email: str, course_title: str) -> str:
    """
    Sends a welcome email to the student.

    In production this would call SendGrid, SES, etc.
    Currently mocked — just logs and returns.

    This activity has a RetryPolicy configured in the workflow,
    so transient failures (email server down) are retried automatically.
    """
    # TODO: Replace with real email provider call
    print(f"[Activity] 📧 Sending welcome email to {email} for '{course_title}'")
    message = f"Welcome email sent to {email} for course '{course_title}'"
    print(f"[Activity] ✅ {message}")
    return message



@workflow.defn
class EnrollmentWorkflow:
    @workflow.run
    async def run(self, input: EnrollmentWorkflowInput) -> dict:
        """
        Orchestrates enrollment in 3 steps.

        If any step fails permanently (non-retryable error), the whole
        workflow fails and nothing further is executed — no partial state.
        """

        # Step 1: Validate (fast, no side effects — fail early if invalid)
        await workflow.execute_activity(
            validate_enrollment_activity,
            args=[input.student_id, input.course_id],
            start_to_close_timeout=timedelta(seconds=10),
        )

        # Step 2: Write enrollment to DB
        # Only runs if validation passed — avoids dirty writes
        enrollment_id = await workflow.execute_activity(
            create_enrollment_activity,
            args=[input.student_id, input.course_id],
            start_to_close_timeout=timedelta(seconds=10),
        )

        # Step 3: Send welcome email — retried up to 3 times if it fails
        # If this fails after all retries, enrollment is still created (step 2 committed).
        # In production you'd handle this with a compensation activity or a signal.
        await workflow.execute_activity(
            send_enrollment_email_activity,
            args=[input.student_email, "SmartCourse"],   # course title placeholder
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=2),
                backoff_coefficient=2.0,
                maximum_attempts=3,
            ),
        )

        return {
            "enrollment_id": enrollment_id,
            "student_id": input.student_id,
            "course_id": input.course_id,
            "status": "enrolled",
        }
