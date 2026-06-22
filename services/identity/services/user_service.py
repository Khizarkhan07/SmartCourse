import uuid

from core.exceptions import ConflictError, NotFoundError
from core.security import hash_password
from models.user import User, UserRole
from repositories.user_repository import UserRepository
from schemas.user import UserCreate


async def create_user(repo: UserRepository, data: UserCreate) -> User:
    if await repo.get_by_email(data.email):
        raise ConflictError("A user with this email already exists")
    user = User(
        name=data.name,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=UserRole.student,
    )
    return await repo.save(user)


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
    return await repo.save(user)


async def soft_delete_user(repo: UserRepository, user_id: uuid.UUID) -> User:
    user = await get_user_by_id(repo, user_id)
    user.is_active = False
    return await repo.save(user)
