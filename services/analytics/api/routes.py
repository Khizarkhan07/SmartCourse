from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import require_instructor_or_admin
from database import AsyncSessionLocal
from repositories.analytics_repository import AnalyticsRepository
from schemas.analytics import (
    AnalyticsOverviewResponse,
    CourseAnalyticsResponse,
    EnrollmentAnalyticsResponse,
    WorkflowAnalyticsResponse,
)
from services import analytics_service

router = APIRouter(tags=["Analytics"])


async def get_repo() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield AnalyticsRepository(session)


@router.get("/overview", response_model=AnalyticsOverviewResponse)
async def get_overview(
    repo: AnalyticsRepository = Depends(get_repo),
    _: dict = Depends(require_instructor_or_admin),
):
    return await analytics_service.get_overview_metrics(repo)


@router.get("/enrollments", response_model=EnrollmentAnalyticsResponse)
async def get_enrollment_analytics(
    days: int = Query(default=30, ge=1, le=365),
    repo: AnalyticsRepository = Depends(get_repo),
    _: dict = Depends(require_instructor_or_admin),
):
    points = await analytics_service.get_enrollments_over_time(repo, days=days)
    total_new = await analytics_service.get_new_enrollments(repo, days=days)
    return {"period_days": days, "total_new_enrollments": total_new, "points": points}


@router.get("/courses", response_model=CourseAnalyticsResponse)
async def get_course_analytics(
    top_n: int = Query(default=5, ge=1, le=20),
    repo: AnalyticsRepository = Depends(get_repo),
    _: dict = Depends(require_instructor_or_admin),
):
    return await analytics_service.get_course_metrics(repo, top_n=top_n)


@router.get("/workflows", response_model=WorkflowAnalyticsResponse)
async def get_workflow_analytics(
    _: dict = Depends(require_instructor_or_admin),
):
    return {"failed_workflow_count": await analytics_service.get_failed_workflow_count()}
