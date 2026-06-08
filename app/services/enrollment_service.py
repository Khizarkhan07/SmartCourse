import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from app.models import (
    Enrollment,
    Course,
    User,
    UserRole,
    CourseStatus,
    Lesson,
    Module,
    LessonCompletion,
    EnrollmentStatus,
)
from app.schemas.enrollment import EnrollmentCreate
from app.temporal_client import ENROLLMENT_TASK_QUEUE, get_temporal_client
from app.workflows.course_completion_workflow import (
    CourseCompletionWorkflow,
    CourseCompletionWorkflowInput,
)


async def create_enrollment(
    db: AsyncSession,
    data: EnrollmentCreate,
) -> Enrollment:
    """
    Create a new enrollment for a student in a course.

    Idempotent: if the student is already enrolled, returns the existing enrollment.

    Raises:
        HTTPException 404: if course or student not found
        HTTPException 400: if course is not published
    """

    # Step 1: Check if enrollment already exists (idempotency)
    existing = await db.execute(
        select(Enrollment).where(
            (Enrollment.student_id == data.student_id)
            & (Enrollment.course_id == data.course_id)
        )
    )
    enrollment = existing.scalar_one_or_none()

    if enrollment:
        return enrollment  # Already enrolled — return as-is

    # Step 2: Validate course exists and is published
    course_result = await db.execute(select(Course).where(Course.id == data.course_id))
    course = course_result.scalar_one_or_none()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {data.course_id} not found",
        )

    if course.status != CourseStatus.published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Course is not published (status: {course.status})",
        )

    # Step 3: Validate student exists
    student_result = await db.execute(select(User).where(User.id == data.student_id))
    student = student_result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student {data.student_id} not found",
        )

    # Step 4: Create new enrollment — progress always starts at 0 (server-controlled)
    new_enrollment = Enrollment(
        student_id=data.student_id,
        course_id=data.course_id,
        progress_percentage=0,
    )

    db.add(new_enrollment)
    await db.commit()
    await db.refresh(new_enrollment)

    return new_enrollment


async def get_enrollment(
    db: AsyncSession,
    enrollment_id: uuid.UUID,
) -> Enrollment:
    """Get a single enrollment by ID. Raises 404 if not found."""
    result = await db.execute(select(Enrollment).where(Enrollment.id == enrollment_id))
    enrollment = result.scalar_one_or_none()

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found",
        )

    return enrollment


async def list_student_enrollments(
    db: AsyncSession,
    student_id: uuid.UUID,
    limit: int = 10,
    offset: int = 0,
) -> list[Enrollment]:
    """List all enrollments for a student with pagination."""
    result = await db.execute(
        select(Enrollment)
        .where(Enrollment.student_id == student_id)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def list_course_students(
    db: AsyncSession,
    course_id: uuid.UUID,
    limit: int = 10,
    offset: int = 0,
) -> list[Enrollment]:
    """List all students enrolled in a course with pagination."""
    result = await db.execute(
        select(Enrollment)
        .where(Enrollment.course_id == course_id)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def _compute_course_progress(
    db: AsyncSession,
    student_id: uuid.UUID,
    course_id: uuid.UUID,
) -> tuple[int, int, int]:
    total_lessons_stmt = (
        select(func.count(Lesson.id))
        .join(Module, Lesson.module_id == Module.id)
        .where(Module.course_id == course_id)
    )
    total_lessons = int((await db.scalar(total_lessons_stmt)) or 0)

    completed_lessons_stmt = (
        select(func.count(LessonCompletion.id))
        .join(Lesson, LessonCompletion.lesson_id == Lesson.id)
        .join(Module, Lesson.module_id == Module.id)
        .where(
            LessonCompletion.student_id == student_id,
            Module.course_id == course_id,
        )
    )
    completed_lessons = int((await db.scalar(completed_lessons_stmt)) or 0)

    if total_lessons == 0:
        progress_percentage = 0
    else:
        progress_percentage = int(round((completed_lessons / total_lessons) * 100))

    return completed_lessons, total_lessons, progress_percentage


async def _trigger_course_completion_if_needed(
    db: AsyncSession,
    enrollment: Enrollment,
) -> None:
    if enrollment.progress_percentage < 100:
        return

    student = await db.get(User, enrollment.student_id)
    course = await db.get(Course, enrollment.course_id)
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
    except WorkflowAlreadyStartedError:
        pass


async def mark_lesson_complete(
    db: AsyncSession,
    lesson_id: uuid.UUID,
    student_id: uuid.UUID,
) -> Enrollment:
    lesson = await db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found",
        )

    module = await db.get(Module, lesson.module_id)
    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not found for lesson",
        )

    enrollment_result = await db.execute(
        select(Enrollment).where(
            Enrollment.student_id == student_id,
            Enrollment.course_id == module.course_id,
        )
    )
    enrollment = enrollment_result.scalar_one_or_none()
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student is not enrolled in this lesson's course",
        )

    completion_result = await db.execute(
        select(LessonCompletion).where(
            LessonCompletion.student_id == student_id,
            LessonCompletion.lesson_id == lesson_id,
        )
    )
    completion = completion_result.scalar_one_or_none()

    if completion is None:
        db.add(LessonCompletion(student_id=student_id, lesson_id=lesson_id))

    completed_lessons, total_lessons, progress_percentage = await _compute_course_progress(
        db,
        student_id=student_id,
        course_id=module.course_id,
    )

    enrollment.progress_percentage = progress_percentage
    if progress_percentage >= 100:
        enrollment.status = EnrollmentStatus.completed

    await db.commit()
    await db.refresh(enrollment)
    await _trigger_course_completion_if_needed(db, enrollment)
    return enrollment


async def get_enrollment_progress(
    db: AsyncSession,
    enrollment_id: uuid.UUID,
    current_user: User,
) -> dict:
    enrollment = await get_enrollment(db, enrollment_id)

    if current_user.role == UserRole.student and enrollment.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own enrollment progress",
        )

    completed_lessons, total_lessons, progress_percentage = await _compute_course_progress(
        db,
        student_id=enrollment.student_id,
        course_id=enrollment.course_id,
    )

    if enrollment.progress_percentage != progress_percentage:
        enrollment.progress_percentage = progress_percentage
        if progress_percentage >= 100:
            enrollment.status = EnrollmentStatus.completed
        await db.commit()
        await db.refresh(enrollment)

    await _trigger_course_completion_if_needed(db, enrollment)

    return {
        "enrollment_id": enrollment.id,
        "student_id": enrollment.student_id,
        "course_id": enrollment.course_id,
        "progress_percentage": enrollment.progress_percentage,
        "completed_lessons": completed_lessons,
        "total_lessons": total_lessons,
        "enrollment_status": enrollment.status,
    }
