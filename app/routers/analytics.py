from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    CourseAnalyticsResponse,
    EnrollmentAnalyticsResponse,
    WorkflowAnalyticsResponse,
)
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/overview", response_model=AnalyticsOverviewResponse)
async def get_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.instructor, UserRole.admin)),
):
    """Return high-level platform metrics for dashboards."""
    _ = current_user
    return await analytics_service.get_overview_metrics(db)


@router.get("/enrollments", response_model=EnrollmentAnalyticsResponse)
async def get_enrollment_analytics(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.instructor, UserRole.admin)),
):
    """Return enrollment time-series for the selected period."""
    _ = current_user
    points = await analytics_service.get_enrollments_over_time(db, days=days)
    return {
        "period_days": days,
        "total_new_enrollments": await analytics_service.get_new_enrollments(db, days=days),
        "points": points,
    }


@router.get("/courses", response_model=CourseAnalyticsResponse)
async def get_course_analytics(
    top_n: int = Query(default=5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.instructor, UserRole.admin)),
):
    """Return completion and course popularity metrics."""
    _ = current_user
    return {
        "completion_rate": await analytics_service.get_completion_rate(db),
        "avg_time_to_complete_days": await analytics_service.get_avg_time_to_complete_days(db),
        "avg_courses_per_student": await analytics_service.get_avg_courses_per_student(db),
        "most_popular_courses": await analytics_service.get_most_popular_courses(db, top_n=top_n),
    }


@router.get("/workflows", response_model=WorkflowAnalyticsResponse)
async def get_workflow_analytics(
    current_user: User = Depends(require_role(UserRole.instructor, UserRole.admin)),
):
    """Return workflow reliability counters from Temporal visibility."""
    _ = current_user
    return {"failed_workflow_count": await analytics_service.get_failed_workflow_count()}
