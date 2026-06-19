from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from models.enrollment_fact import EnrollmentFact


class EnrollmentFactRepository:
    """Async version — used by the FastAPI API."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_enrollment_id(self, enrollment_id: str) -> EnrollmentFact | None:
        result = await self.session.execute(
            select(EnrollmentFact).where(EnrollmentFact.enrollment_id == enrollment_id)
        )
        return result.scalar_one_or_none()

    async def create(self, fact: EnrollmentFact) -> EnrollmentFact:
        self.session.add(fact)
        await self.session.commit()
        await self.session.refresh(fact)
        return fact


class SyncEnrollmentFactRepository:
    """Sync version — used by Kafka consumers running in threads."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_enrollment_id(self, enrollment_id: str) -> EnrollmentFact | None:
        return self.session.execute(
            select(EnrollmentFact).where(EnrollmentFact.enrollment_id == enrollment_id)
        ).scalar_one_or_none()

    def create(self, fact: EnrollmentFact) -> EnrollmentFact:
        self.session.add(fact)
        self.session.commit()
        self.session.refresh(fact)
        return fact

    def mark_completed(
        self, enrollment_id: str, completed_at: datetime, course_title: str
    ) -> bool:
        fact = self.get_by_enrollment_id(enrollment_id)
        if fact is None:
            return False
        fact.status = "completed"
        fact.completed_at = completed_at
        fact.course_title = course_title
        fact.updated_at = datetime.now(timezone.utc)
        self.session.commit()
        return True
