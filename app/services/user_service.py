import uuid

from app.models.user import User, UserRole
from app.schemas.user import UserCreate
from app.core.security import hash_password
from app.core.exceptions import NotFoundError, ConflictError
from app.infrastructure.database.unit_of_work import UnitOfWork
from app.repositories.user_repository import UserRepository


def _users_repo(uow: UnitOfWork) -> UserRepository:
    if uow.users is None:
        raise RuntimeError("UnitOfWork is not initialized")
    return uow.users


async def create_user(uow: UnitOfWork, data: UserCreate) -> User:
    """
    Register a new user.
    - Checks for duplicate email first
    - Hashes the password before storing
    
    Raises:
        ConflictError: if email already exists
    """
    # Check if email already exists
    existing = await _users_repo(uow).get_by_email(data.email)

    if existing:
        raise ConflictError("A user with this email already exists")

    # Create the user object — note: hash password, never store plain text
    # New users always start as students; only admins can promote them later
    new_user = User(
        name=data.name,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=UserRole.student,
    )

    if uow.session is None:
        raise RuntimeError("UnitOfWork session is not initialized")

    uow.session.add(new_user)
    await uow.commit()
    await uow.session.refresh(new_user)  # reload from DB to get generated fields (id, created_at)
    return new_user


async def get_user_by_id(uow: UnitOfWork, user_id: uuid.UUID) -> User:
    """Fetch a single user by ID. Raises NotFoundError if not found."""
    user = await _users_repo(uow).get_by_id(user_id)

    if not user:
        raise NotFoundError("User not found")
    return user


async def get_user_by_email(uow: UnitOfWork, email: str) -> User | None:
    """Fetch a user by email. Returns None if not found (used for login)."""
    return await _users_repo(uow).get_by_email(email)


async def list_users(uow: UnitOfWork, limit: int = 20, offset: int = 0, include_inactive: bool = False) -> list[User]:
    """
    Return active users with pagination. Default page size is 20. Ordered by creation date (newest first).
    - include_inactive: if True, also returns deactivated users (admin use only)
    """
    return await _users_repo(uow).list_users(
        limit=limit,
        offset=offset,
        include_inactive=include_inactive,
    )


async def update_user_role(uow: UnitOfWork, user_id: uuid.UUID, new_role: UserRole) -> User:
    """
    Update a user's role. Only admins can call this via the API.
    
    Raises:
        - 404 if user not found
    """
    user = await get_user_by_id(uow, user_id)
    user.role = new_role
    if uow.session is None:
        raise RuntimeError("UnitOfWork session is not initialized")

    uow.session.add(user)
    await uow.commit()
    await uow.session.refresh(user)
    return user


async def soft_delete_user(uow: UnitOfWork, user_id: uuid.UUID) -> User:
    """
    Soft delete a user by setting is_active = False.
    
    This preserves user data for auditing and allows courses/enrollments to remain intact.
    Foreign key constraints (RESTRICT) prevent hard deletion if user has related records.
    
    Raises:
        - 404 if user not found
    """
    user = await get_user_by_id(uow, user_id)
    user.is_active = False
    if uow.session is None:
        raise RuntimeError("UnitOfWork session is not initialized")

    uow.session.add(user)
    await uow.commit()
    await uow.session.refresh(user)
    return user
