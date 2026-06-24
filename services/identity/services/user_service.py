import asyncio
import uuid

from core.exceptions import ConflictError, NotFoundError
from core.logging import get_logger
from core.security import hash_password
from models.user import User, UserRole
from repositories.user_repository import UserRepository
from schemas.user import UserCreate

logger = get_logger(__name__)


def _emit(user: User) -> None:
    """Fire-and-forget Kafka emit. Runs in a thread so it doesn't block the event loop."""
    try:
        from events.producer import produce_user_profile_updated
        produce_user_profile_updated(
            str(user.id), user.name, user.email, user.role.value, user.is_active
        )
    except Exception as exc:
        logger.warning("user.profile_updated emit failed", error=str(exc))


async def create_user(repo: UserRepository, data: UserCreate) -> User:
    if await repo.get_by_email(data.email):
        raise ConflictError("A user with this email already exists")
    user = User(
        name=data.name,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=UserRole.student,
    )
    result = await repo.save(user)
    asyncio.get_event_loop().run_in_executor(None, _emit, result)
    return result


async def get_user_by_id(repo: UserRepository, user_id: uuid.UUID) -> User:
    user = await repo.get_by_id(user_id)
    if not user:
        raise NotFoundError("User not found")
    return user


async def get_user_by_email(repo: UserRepository, email: str) -> User | None:
    return await repo.get_by_email(email)


async def list_users(repo: UserRepository, limit: int, offset: int) -> list[User]:
    return await repo.list_users(limit=limit, offset=offset)


async def update_user_role(repo: UserRepository, user_id: uuid.UUID, new_role: UserRole) -> User:
    user = await get_user_by_id(repo, user_id)
    user.role = new_role
    result = await repo.save(user)
    asyncio.get_event_loop().run_in_executor(None, _emit, result)
    return result


async def soft_delete_user(repo: UserRepository, user_id: uuid.UUID) -> User:
    user = await get_user_by_id(repo, user_id)
    user.is_active = False
    result = await repo.save(user)
    asyncio.get_event_loop().run_in_executor(None, _emit, result)
    return result
