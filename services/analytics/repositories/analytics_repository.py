from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.course_fact import CourseFact
from models.enrollment_fact import EnrollmentFact


class AnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_distinct_students(self) -> int:
        stmt = select(func.count(func.distinct(EnrollmentFact.student_id)))
        return int((await self.session.scalar(stmt)) or 0)

    async def count_distinct_instructors(self) -> int:
        stmt = select(func.count(func.distinct(CourseFact.instructor_id)))
        return int((await self.session.scalar(stmt)) or 0)

    async def count_published_courses(self) -> int:
        stmt = select(func.count(CourseFact.course_id)).where(CourseFact.status == "published")
        return int((await self.session.scalar(stmt)) or 0)

    async def count_new_enrollments_since(self, since: datetime) -> int:
        stmt = select(func.count(EnrollmentFact.id)).where(EnrollmentFact.enrolled_at >= since)
        return int((await self.session.scalar(stmt)) or 0)

    async def count_total_enrollments(self) -> int:
        return int((await self.session.scalar(select(func.count(EnrollmentFact.id)))) or 0)

    async def count_completed_enrollments(self) -> int:
        stmt = select(func.count(EnrollmentFact.id)).where(EnrollmentFact.status == "completed")
        return int((await self.session.scalar(stmt)) or 0)

    async def avg_time_to_complete_days(self) -> float:
        stmt = select(
            func.avg(
                func.extract("epoch", EnrollmentFact.completed_at - EnrollmentFact.enrolled_at)
                / 86400.0
            )
        ).where(
            EnrollmentFact.status == "completed",
            EnrollmentFact.completed_at.isnot(None),
        )
        value = (await self.session.scalar(stmt)) or 0.0
        return float(value)

    async def most_popular_courses(self, top_n: int) -> list[dict]:
        stmt = (
            select(
                EnrollmentFact.course_id,
                CourseFact.title,
                func.count(EnrollmentFact.id).label("enrollment_count"),
            )
            .outerjoin(CourseFact, CourseFact.course_id == EnrollmentFact.course_id)
            .group_by(EnrollmentFact.course_id, CourseFact.title)
            .order_by(func.count(EnrollmentFact.id).desc())
            .limit(top_n)
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "course_id": str(row.course_id),
                "title": row.title or "",
                "enrollment_count": int(row.enrollment_count),
            }
            for row in rows
        ]

    async def count_distinct_enrolled_students(self) -> int:
        stmt = select(func.count(func.distinct(EnrollmentFact.student_id)))
        return int((await self.session.scalar(stmt)) or 0)

    async def enrollments_over_time(self, since: datetime) -> list[dict]:
        day_bucket = func.date_trunc("day", EnrollmentFact.enrolled_at)
        stmt = (
            select(day_bucket.label("day"), func.count(EnrollmentFact.id).label("enrollments"))
            .where(EnrollmentFact.enrolled_at >= since)
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
