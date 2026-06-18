import uuid
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from app.models import (
    Enrollment,
    User,
    UserRole,
    CourseStatus,
    LessonCompletion,
    EnrollmentStatus,
)
from app.schemas.enrollment import EnrollmentCreate
from app.infrastructure.temporal import ENROLLMENT_TASK_QUEUE, get_temporal_client
from app.workflows.course_completion_workflow import (
    CourseCompletionWorkflow,
    CourseCompletionWorkflowInput,
)
from app.core.exceptions import NotFoundError, ValidationError, PermissionDeniedError
from app.core.metrics import completions_total, workflow_failures_total
from app.infrastructure.database.unit_of_work import UnitOfWork
from app.repositories.course_repository import CourseRepository
from app.repositories.enrollment_repository import EnrollmentRepository
from app.repositories.user_repository import UserRepository


def _enrollments_repo(uow: UnitOfWork) -> EnrollmentRepository:
    if uow.enrollments is None:
        raise RuntimeError("UnitOfWork is not initialized")
    return uow.enrollments


def _courses_repo(uow: UnitOfWork) -> CourseRepository:
    if uow.courses is None:
        raise RuntimeError("UnitOfWork is not initialized")
    return uow.courses


def _users_repo(uow: UnitOfWork) -> UserRepository:
    if uow.users is None:
        raise RuntimeError("UnitOfWork is not initialized")
    return uow.users


async def create_enrollment(
    uow: UnitOfWork,
    data: EnrollmentCreate,
) -> Enrollment:
    """
    Create a new enrollment for a student in a course.

    Idempotent: if the student is already enrolled, returns the existing enrollment.

    Raises:
        NotFoundError: if course or student not found
        ValidationError: if course is not published
    """

    if uow.session is None:
        raise RuntimeError("UnitOfWork session is not initialized")

    repo = _enrollments_repo(uow)

    # Step 1: Check if enrollment already exists (idempotency)
    enrollment = await repo.get_by_student_course(data.student_id, data.course_id)

    if enrollment:
        return enrollment  # Already enrolled — return as-is

    # Step 2: Validate course exists and is published
    course = await _courses_repo(uow).get_course_by_id(data.course_id)

    if not course:
        raise NotFoundError(f"Course {data.course_id} not found")

    if course.status != CourseStatus.published:
        raise ValidationError(f"Course is not published (status: {course.status})")

    # Step 3: Validate student exists
    student = await _users_repo(uow).get_by_id(data.student_id)

    if not student:
        raise NotFoundError(f"Student {data.student_id} not found")

    # Step 4: Create new enrollment — progress always starts at 0 (server-controlled)
    new_enrollment = Enrollment(
        student_id=data.student_id,
        course_id=data.course_id,
        progress_percentage=0,
    )

    uow.session.add(new_enrollment)
    await uow.commit()
    await uow.session.refresh(new_enrollment)

    return new_enrollment


async def get_enrollment(
    uow: UnitOfWork,
    enrollment_id: uuid.UUID,
) -> Enrollment:
    """Get a single enrollment by ID. Raises NotFoundError if not found."""
    enrollment = await _enrollments_repo(uow).get_by_id(enrollment_id)

    if not enrollment:
        raise NotFoundError("Enrollment not found")

    return enrollment


async def list_student_enrollments(
    uow: UnitOfWork,
    student_id: uuid.UUID,
    limit: int = 10,
    offset: int = 0,
) -> list[Enrollment]:
    """List all enrollments for a student with pagination. Ordered by creation date (newest first)."""
    return await _enrollments_repo(uow).list_by_student(
        student_id,
        limit=limit,
        offset=offset,
    )


async def list_course_students(
    uow: UnitOfWork,
    course_id: uuid.UUID,
    limit: int = 10,
    offset: int = 0,
) -> list[Enrollment]:
    """List all students enrolled in a course with pagination. Ordered by creation date (newest first)."""
    return await _enrollments_repo(uow).list_by_course(
        course_id,
        limit=limit,
        offset=offset,
    )


async def _compute_course_progress(
    uow: UnitOfWork,
    student_id: uuid.UUID,
    course_id: uuid.UUID,
) -> tuple[int, int, int]:
    repo = _enrollments_repo(uow)
    total_lessons = await repo.count_total_lessons(course_id)
    completed_lessons = await repo.count_completed_lessons(student_id, course_id)

    if total_lessons == 0:
        progress_percentage = 0
    else:
        progress_percentage = int(round((completed_lessons / total_lessons) * 100))

    return completed_lessons, total_lessons, progress_percentage


async def _trigger_course_completion_if_needed(
    uow: UnitOfWork,
    enrollment: Enrollment,
) -> None:
    if enrollment.progress_percentage < 100:
        return

    student = await _users_repo(uow).get_by_id(enrollment.student_id)
    course = await _courses_repo(uow).get_course_by_id(enrollment.course_id)
    if not student or not course:
        return

    workflow_id = f"complete-{enrollment.id}"
    client = await get_temporal_client()

    try:
        await client.start_workflow(
            CourseCompletionWorkflow.run,
            CourseCompletionWorkflowInput(
                enrollment_id=str(enrollment.id),
                student_id=str(enrollment.student_id),
                student_email=student.email,
                course_id=str(enrollment.course_id),
                course_title=course.title,
            ),
            id=workflow_id,
            task_queue=ENROLLMENT_TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
        completions_total.inc()
    except WorkflowAlreadyStartedError:
        pass
    except Exception:
        workflow_failures_total.labels(workflow="completion").inc()
        raise


async def mark_lesson_complete(
    uow: UnitOfWork,
    lesson_id: uuid.UUID,
    student_id: uuid.UUID,
) -> Enrollment:
    if uow.session is None:
        raise RuntimeError("UnitOfWork session is not initialized")

    repo = _enrollments_repo(uow)

    lesson = await repo.get_lesson_by_id(lesson_id)
    if not lesson:
        raise NotFoundError("Lesson not found")

    module = await repo.get_module_by_id(lesson.module_id)
    if not module:
        raise NotFoundError("Module not found for lesson")

    enrollment = await repo.get_by_student_course(
        student_id=student_id,
        course_id=module.course_id,
    )
    if not enrollment:
        raise ValidationError("Student is not enrolled in this lesson's course")

    completion = await repo.get_lesson_completion(
        student_id=student_id,
        lesson_id=lesson_id,
    )

    if completion is None:
        uow.session.add(LessonCompletion(student_id=student_id, lesson_id=lesson_id))

    completed_lessons, total_lessons, progress_percentage = await _compute_course_progress(
        uow,
        student_id=student_id,
        course_id=module.course_id,
    )

    enrollment.progress_percentage = progress_percentage
    if progress_percentage >= 100:
        enrollment.status = EnrollmentStatus.completed

    await uow.commit()
    await uow.session.refresh(enrollment)
    await _trigger_course_completion_if_needed(uow, enrollment)
    return enrollment


async def get_enrollment_progress(
    uow: UnitOfWork,
    enrollment_id: uuid.UUID,
    current_user: User,
) -> dict:
    if uow.session is None:
        raise RuntimeError("UnitOfWork session is not initialized")

    enrollment = await get_enrollment(uow, enrollment_id)

    if current_user.role == UserRole.student and enrollment.student_id != current_user.id:
        raise PermissionDeniedError("You can only view your own enrollment progress")

    completed_lessons, total_lessons, progress_percentage = await _compute_course_progress(
        uow,
        student_id=enrollment.student_id,
        course_id=enrollment.course_id,
    )

    if enrollment.progress_percentage != progress_percentage:
        enrollment.progress_percentage = progress_percentage
        if progress_percentage >= 100:
            enrollment.status = EnrollmentStatus.completed
        await uow.commit()
        await uow.session.refresh(enrollment)

    await _trigger_course_completion_if_needed(uow, enrollment)

    return {
        "enrollment_id": enrollment.id,
        "student_id": enrollment.student_id,
        "course_id": enrollment.course_id,
        "progress_percentage": enrollment.progress_percentage,
        "completed_lessons": completed_lessons,
        "total_lessons": total_lessons,
        "enrollment_status": enrollment.status,
    }
