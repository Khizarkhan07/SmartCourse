import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.module import Module


class ModuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, module_id: uuid.UUID) -> Module | None:
        result = await self.session.execute(select(Module).where(Module.id == module_id))
        return result.scalar_one_or_none()

    async def list_by_course(self, course_id: uuid.UUID) -> list[Module]:
        result = await self.session.execute(
            select(Module).where(Module.course_id == course_id).order_by(Module.order)
        )
        return list(result.scalars().all())
