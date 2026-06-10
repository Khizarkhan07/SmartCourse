from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course, CourseStatus
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.user import User, UserRole


class AnalyticsRepository:
    """Data-access operations for analytics/reporting queries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_active_students(self) -> int:
        stmt = select(func.count(User.id)).where(
            User.role == UserRole.student,
            User.is_active.is_(True),
        )
        return int((await self.session.scalar(stmt)) or 0)

    async def count_active_instructors(self) -> int:
        stmt = select(func.count(User.id)).where(
            User.role == UserRole.instructor,
            User.is_active.is_(True),
        )
        return int((await self.session.scalar(stmt)) or 0)

    async def count_published_courses(self) -> int:
        stmt = select(func.count(Course.id)).where(
            Course.status == CourseStatus.published,
            Course.is_active.is_(True),
        )
        return int((await self.session.scalar(stmt)) or 0)

    async def count_new_enrollments_since(self, since: datetime) -> int:
        stmt = select(func.count(Enrollment.id)).where(Enrollment.enrolled_at >= since)
        return int((await self.session.scalar(stmt)) or 0)

    async def count_total_enrollments(self) -> int:
        return int((await self.session.scalar(select(func.count(Enrollment.id)))) or 0)

    async def count_completed_enrollments(self) -> int:
        stmt = select(func.count(Enrollment.id)).where(
            Enrollment.status == EnrollmentStatus.completed
        )
        return int((await self.session.scalar(stmt)) or 0)

    async def avg_time_to_complete_days(self) -> float:
        stmt = select(
            func.avg(
                func.extract("epoch", Enrollment.updated_at - Enrollment.enrolled_at)
                / 86400.0
            )
        ).where(Enrollment.status == EnrollmentStatus.completed)
        value = (await self.session.scalar(stmt)) or 0.0
        return float(value)

    async def most_popular_courses(self, top_n: int) -> list[dict]:
        stmt = (
            select(
                Course.id,
                Course.title,
                func.count(Enrollment.id).label("enrollment_count"),
            )
            .join(Enrollment, Enrollment.course_id == Course.id)
            .group_by(Course.id, Course.title)
            .order_by(func.count(Enrollment.id).desc())
            .limit(top_n)
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "course_id": str(row.id),
                "title": row.title,
                "enrollment_count": int(row.enrollment_count),
            }
            for row in rows
        ]

    async def count_distinct_enrolled_students(self) -> int:
        stmt = select(func.count(func.distinct(Enrollment.student_id)))
        return int((await self.session.scalar(stmt)) or 0)

    async def enrollments_over_time(self, since: datetime) -> list[dict]:
        day_bucket = func.date_trunc("day", Enrollment.enrolled_at)
        stmt = (
            select(day_bucket.label("day"), func.count(Enrollment.id).label("enrollments"))
            .where(Enrollment.enrolled_at >= since)
            .group_by(day_bucket)
            .order_by(day_bucket)
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "date": row.day.date(),
                "enrollments": int(row.enrollments),
            }
            for row in rows
        ]
