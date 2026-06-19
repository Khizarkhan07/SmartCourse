from datetime import datetime, timedelta, timezone

from infrastructure.cache import cache_get, cache_set
from infrastructure.temporal import get_temporal_client
from repositories.analytics_repository import AnalyticsRepository

TRACKED_WORKFLOW_TYPES = {
    "EnrollmentWorkflow",
    "PublishCourseWorkflow",
    "ArchiveCourseWorkflow",
}


async def get_overview_metrics(repo: AnalyticsRepository) -> dict:
    cached = await cache_get("analytics:overview")
    if cached is not None:
        return cached

    result = {
        "total_students": await repo.count_distinct_students(),
        "total_instructors": await repo.count_distinct_instructors(),
        "total_courses_published": await repo.count_published_courses(),
        "new_enrollments_last_30_days": await repo.count_new_enrollments_since(
            datetime.now(timezone.utc) - timedelta(days=30)
        ),
        "course_completion_rate": await _get_completion_rate(repo),
        "avg_time_to_complete_days": round(await repo.avg_time_to_complete_days(), 2),
        "avg_courses_per_student": await _get_avg_courses_per_student(repo),
        "failed_workflow_count": await get_failed_workflow_count(),
        "most_popular_courses": await _get_most_popular_courses(repo, top_n=5),
    }
    await cache_set("analytics:overview", result, ttl=60)
    return result


async def get_enrollments_over_time(repo: AnalyticsRepository, days: int) -> list[dict]:
    key = f"analytics:enrollments_over_time:{days}"
    cached = await cache_get(key)
    if cached is not None:
        return cached
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await repo.enrollments_over_time(since)
    await cache_set(key, result, ttl=60)
    return result


async def get_new_enrollments(repo: AnalyticsRepository, days: int) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    return await repo.count_new_enrollments_since(since)


async def get_course_metrics(repo: AnalyticsRepository, top_n: int) -> dict:
    return {
        "completion_rate": await _get_completion_rate(repo),
        "avg_time_to_complete_days": round(await repo.avg_time_to_complete_days(), 2),
        "avg_courses_per_student": await _get_avg_courses_per_student(repo),
        "most_popular_courses": await _get_most_popular_courses(repo, top_n=top_n),
    }


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
        return count
    except Exception:
        return 0


async def _get_completion_rate(repo: AnalyticsRepository) -> float:
    total = await repo.count_total_enrollments()
    if total == 0:
        return 0.0
    completed = await repo.count_completed_enrollments()
    return round(completed / total, 4)


async def _get_avg_courses_per_student(repo: AnalyticsRepository) -> float:
    total = await repo.count_total_enrollments()
    unique = await repo.count_distinct_enrolled_students()
    if unique == 0:
        return 0.0
    return round(total / unique, 2)


async def _get_most_popular_courses(repo: AnalyticsRepository, top_n: int) -> list[dict]:
    key = f"analytics:popular_courses:{top_n}"
    cached = await cache_get(key)
    if cached is not None:
        return cached
    result = await repo.most_popular_courses(top_n)
    await cache_set(key, result, ttl=60)
    return result
