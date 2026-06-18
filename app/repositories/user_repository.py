import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Data-access operations for User entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def list_users(
        self,
        *,
        limit: int,
        offset: int,
        include_inactive: bool,
    ) -> list[User]:
        query = select(User)
        if not include_inactive:
            query = query.where(User.is_active.is_(True))

        result = await self.session.execute(
            query.order_by(User.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
