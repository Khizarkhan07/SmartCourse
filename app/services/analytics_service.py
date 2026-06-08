from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course, CourseStatus
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.user import User, UserRole
from app.temporal_client import get_temporal_client

TRACKED_WORKFLOW_TYPES = {
    "EnrollmentWorkflow",
    "PublishCourseWorkflow",
    "ArchiveCourseWorkflow",
}


async def get_total_students(db: AsyncSession) -> int:
    stmt = select(func.count(User.id)).where(
        User.role == UserRole.student,
        User.is_active.is_(True),
    )
    return int((await db.scalar(stmt)) or 0)


async def get_total_instructors(db: AsyncSession) -> int:
    stmt = select(func.count(User.id)).where(
        User.role == UserRole.instructor,
        User.is_active.is_(True),
    )
    return int((await db.scalar(stmt)) or 0)


async def get_total_courses_published(db: AsyncSession) -> int:
    stmt = select(func.count(Course.id)).where(
        Course.status == CourseStatus.published,
        Course.is_active.is_(True),
    )
    return int((await db.scalar(stmt)) or 0)


async def get_new_enrollments(db: AsyncSession, days: int = 30) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = select(func.count(Enrollment.id)).where(Enrollment.enrolled_at >= since)
    return int((await db.scalar(stmt)) or 0)


async def get_completion_rate(db: AsyncSession) -> float:
    total_stmt = select(func.count(Enrollment.id))
    completed_stmt = select(func.count(Enrollment.id)).where(
        Enrollment.status == EnrollmentStatus.completed
    )
    total = int((await db.scalar(total_stmt)) or 0)
    if total == 0:
        return 0.0
    completed = int((await db.scalar(completed_stmt)) or 0)
    return round(completed / total, 4)


async def get_avg_time_to_complete_days(db: AsyncSession) -> float:
    stmt = select(
        func.avg(
            func.extract("epoch", Enrollment.updated_at - Enrollment.enrolled_at)
            / 86400.0
        )
    ).where(Enrollment.status == EnrollmentStatus.completed)
    value = (await db.scalar(stmt)) or 0.0
    return round(float(value), 2)


async def get_most_popular_courses(db: AsyncSession, top_n: int = 5) -> list[dict]:
    stmt = (
        select(Course.id, Course.title, func.count(Enrollment.id).label("enrollment_count"))
        .join(Enrollment, Enrollment.course_id == Course.id)
        .group_by(Course.id, Course.title)
        .order_by(func.count(Enrollment.id).desc())
        .limit(top_n)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "course_id": str(row.id),
            "title": row.title,
            "enrollment_count": int(row.enrollment_count),
        }
        for row in rows
    ]


async def get_avg_courses_per_student(db: AsyncSession) -> float:
    total_enrollments = int((await db.scalar(select(func.count(Enrollment.id)))) or 0)
    unique_students = int(
        (await db.scalar(select(func.count(func.distinct(Enrollment.student_id))))) or 0
    )
    if unique_students == 0:
        return 0.0
    return round(total_enrollments / unique_students, 2)


async def get_enrollments_over_time(db: AsyncSession, days: int = 30) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    day_bucket = func.date_trunc("day", Enrollment.enrolled_at)
    stmt = (
        select(day_bucket.label("day"), func.count(Enrollment.id).label("enrollments"))
        .where(Enrollment.enrolled_at >= since)
        .group_by(day_bucket)
        .order_by(day_bucket)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "date": row.day.date(),
            "enrollments": int(row.enrollments),
        }
        for row in rows
    ]


async def get_failed_workflow_count() -> int:
    try:
        client = await get_temporal_client()
        count = 0

        async for execution in client.list_workflows("ExecutionStatus='Failed'"):
            workflow_type = None
            execution_type = getattr(execution, "type", None)
            if execution_type is not None:
                workflow_type = getattr(execution_type, "name", None) or str(execution_type)

            if workflow_type in TRACKED_WORKFLOW_TYPES:
                count += 1
    except Exception:
        # Keep analytics endpoint resilient if Temporal visibility is unavailable.
        return 0

    return count


async def get_overview_metrics(db: AsyncSession) -> dict:
    return {
        "total_students": await get_total_students(db),
        "total_instructors": await get_total_instructors(db),
        "total_courses_published": await get_total_courses_published(db),
        "new_enrollments_last_30_days": await get_new_enrollments(db, days=30),
        "course_completion_rate": await get_completion_rate(db),
        "avg_time_to_complete_days": await get_avg_time_to_complete_days(db),
        "avg_courses_per_student": await get_avg_courses_per_student(db),
        "failed_workflow_count": await get_failed_workflow_count(),
        "most_popular_courses": await get_most_popular_courses(db, top_n=5),
    }
