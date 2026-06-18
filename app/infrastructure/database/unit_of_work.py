from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import AsyncSessionLocal
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.enrollment_repository import EnrollmentRepository
from app.repositories.lesson_repository import LessonRepository
from app.repositories.module_repository import ModuleRepository
from app.repositories.user_repository import UserRepository


class UnitOfWork:
    """Explicit transaction boundary.

    This is intentionally minimal for chunked adoption.
    Existing flows can continue using AsyncSession directly until migrated.
    """

    def __init__(self) -> None:
        self.session: AsyncSession | None = None
        self.users: UserRepository | None = None
        self.courses: CourseRepository | None = None
        self.enrollments: EnrollmentRepository | None = None
        self.modules: ModuleRepository | None = None
        self.lessons: LessonRepository | None = None
        self.analytics: AnalyticsRepository | None = None

    async def __aenter__(self) -> "UnitOfWork":
        self.session = AsyncSessionLocal()
        self.users = UserRepository(self.session)
        self.courses = CourseRepository(self.session)
        self.enrollments = EnrollmentRepository(self.session)
        self.modules = ModuleRepository(self.session)
        self.lessons = LessonRepository(self.session)
        self.analytics = AnalyticsRepository(self.session)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.session is None:
            return
        if exc is not None:
            await self.session.rollback()
        await self.session.close()

    async def commit(self) -> None:
        if self.session is None:
            raise RuntimeError("UnitOfWork session is not initialized")
        await self.session.commit()

    async def rollback(self) -> None:
        if self.session is None:
            return
        await self.session.rollback()


async def get_uow() -> AsyncGenerator[UnitOfWork, None]:
    """FastAPI dependency for request-scoped UnitOfWork."""
    async with UnitOfWork() as uow:
        yield uow
