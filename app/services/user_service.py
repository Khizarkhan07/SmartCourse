import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User, UserRole
from app.schemas.user import UserCreate
from app.security import hash_password
from app.exceptions import NotFoundError, ConflictError


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    """
    Register a new user.
    - Checks for duplicate email first
    - Hashes the password before storing
    
    Raises:
        ConflictError: if email already exists
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == data.email))
    existing = result.scalar_one_or_none()

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

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)  # reload from DB to get generated fields (id, created_at)
    return new_user


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User:
    """Fetch a single user by ID. Raises NotFoundError if not found."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError("User not found")
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Fetch a user by email. Returns None if not found (used for login)."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def list_users(db: AsyncSession, limit: int = 20, offset: int = 0, include_inactive: bool = False) -> list[User]:
    """
    Return active users with pagination. Default page size is 20. Ordered by creation date (newest first).
    - include_inactive: if True, also returns deactivated users (admin use only)
    """
    query = select(User)
    
    if not include_inactive:
        query = query.where(User.is_active.is_(True))
    
    result = await db.execute(
        query
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
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


async def soft_delete_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    """
    Soft delete a user by setting is_active = False.
    
    This preserves user data for auditing and allows courses/enrollments to remain intact.
    Foreign key constraints (RESTRICT) prevent hard deletion if user has related records.
    
    Raises:
        - 404 if user not found
    """
    user = await get_user_by_id(db, user_id)
    user.is_active = False
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
