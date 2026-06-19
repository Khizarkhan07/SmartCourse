from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from models.course_fact import CourseFact


class CourseFactRepository:
    """Async version — used by the FastAPI API."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_course_id(self, course_id: str) -> CourseFact | None:
        result = await self.session.execute(
            select(CourseFact).where(CourseFact.course_id == course_id)
        )
        return result.scalar_one_or_none()


class SyncCourseFactRepository:
    """Sync version — used by Kafka consumers running in threads."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_course_id(self, course_id: str) -> CourseFact | None:
        return self.session.execute(
            select(CourseFact).where(CourseFact.course_id == course_id)
        ).scalar_one_or_none()

    def upsert(self, fact: CourseFact) -> CourseFact:
        existing = self.get_by_course_id(fact.course_id)
        if existing:
            existing.title = fact.title
            existing.status = fact.status
            existing.updated_at = datetime.now(timezone.utc)
            self.session.commit()
            return existing
        self.session.add(fact)
        self.session.commit()
        self.session.refresh(fact)
        return fact
