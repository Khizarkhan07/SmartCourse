from datetime import datetime, timedelta, timezone

from app.infrastructure.database.unit_of_work import UnitOfWork
from app.repositories.analytics_repository import AnalyticsRepository
from app.infrastructure.temporal import get_temporal_client

TRACKED_WORKFLOW_TYPES = {
    "EnrollmentWorkflow",
    "PublishCourseWorkflow",
    "ArchiveCourseWorkflow",
}


def _analytics_repo(uow: UnitOfWork) -> AnalyticsRepository:
    if uow.analytics is None:
        raise RuntimeError("UnitOfWork is not initialized")
    return uow.analytics


async def get_total_students(uow: UnitOfWork) -> int:
    return await _analytics_repo(uow).count_active_students()


async def get_total_instructors(uow: UnitOfWork) -> int:
    return await _analytics_repo(uow).count_active_instructors()


async def get_total_courses_published(uow: UnitOfWork) -> int:
    return await _analytics_repo(uow).count_published_courses()


async def get_new_enrollments(uow: UnitOfWork, days: int = 30) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    return await _analytics_repo(uow).count_new_enrollments_since(since)


async def get_completion_rate(uow: UnitOfWork) -> float:
    repo = _analytics_repo(uow)
    total = await repo.count_total_enrollments()
    if total == 0:
        return 0.0
    completed = await repo.count_completed_enrollments()
    return round(completed / total, 4)


async def get_avg_time_to_complete_days(uow: UnitOfWork) -> float:
    value = await _analytics_repo(uow).avg_time_to_complete_days()
    return round(float(value), 2)


async def get_most_popular_courses(uow: UnitOfWork, top_n: int = 5) -> list[dict]:
    return await _analytics_repo(uow).most_popular_courses(top_n)


async def get_avg_courses_per_student(uow: UnitOfWork) -> float:
    repo = _analytics_repo(uow)
    total_enrollments = await repo.count_total_enrollments()
    unique_students = await repo.count_distinct_enrolled_students()
    if unique_students == 0:
        return 0.0
    return round(total_enrollments / unique_students, 2)


async def get_enrollments_over_time(uow: UnitOfWork, days: int = 30) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    return await _analytics_repo(uow).enrollments_over_time(since)


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


async def get_overview_metrics(uow: UnitOfWork) -> dict:
    return {
        "total_students": await get_total_students(uow),
        "total_instructors": await get_total_instructors(uow),
        "total_courses_published": await get_total_courses_published(uow),
        "new_enrollments_last_30_days": await get_new_enrollments(uow, days=30),
        "course_completion_rate": await get_completion_rate(uow),
        "avg_time_to_complete_days": await get_avg_time_to_complete_days(uow),
        "avg_courses_per_student": await get_avg_courses_per_student(uow),
        "failed_workflow_count": await get_failed_workflow_count(),
        "most_popular_courses": await get_most_popular_courses(uow, top_n=5),
    }
