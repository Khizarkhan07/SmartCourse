import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.user import User, UserRole
from app.schemas.user import UserCreate
from app.security import hash_password


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    """
    Register a new user.
    - Checks for duplicate email first
    - Hashes the password before storing
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == data.email))
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    # Create the user object — note: hash password, never store plain text
    # New users always start as students; only admins can promote them later
    new_user = User(
        name=data.name,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=UserRole.student,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)  # reload from DB to get generated fields (id, created_at)
    return new_user


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User:
    """Fetch a single user by ID. Raises 404 if not found."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Fetch a user by email. Returns None if not found (used for login)."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def list_users(db: AsyncSession, limit: int = 20, offset: int = 0) -> list[User]:
    """Return users with pagination. Default page size is 20."""
    result = await db.execute(select(User).limit(limit).offset(offset))
    return list(result.scalars().all())


async def update_user_role(db: AsyncSession, user_id: uuid.UUID, new_role: UserRole) -> User:
    """
    Update a user's role. Only admins can call this via the API.
    
    Raises:
        - 404 if user not found
    """
    user = await get_user_by_id(db, user_id)
    user.role = new_role
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
