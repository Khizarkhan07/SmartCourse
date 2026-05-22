from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Callable

from app.config import settings
from app.database import get_db
from app.models.user import UserRole

# This tells FastAPI:
# "Protected routes expect a Bearer token at /auth/login"
# It also adds a padlock icon on those routes in /docs so you can test auth there
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def create_access_token(data: dict) -> str:
    """
    Create a signed JWT token.

    `data` is the payload — what we want to store inside the token.
    We always add an expiry time (exp) so tokens don't live forever.

    Example payload stored inside the token:
        { "sub": "user-uuid-here", "role": "instructor", "exp": 1234567890 }
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire

    # jwt.encode signs the payload with our SECRET_KEY
    # Only someone with the SECRET_KEY can create a valid signature
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """
    Decode and verify a JWT token.

    Returns the payload dict if valid, None if expired or tampered.
    jose automatically verifies:
    - The signature (was it signed with our SECRET_KEY?)
    - The expiry (has it expired?)
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """
    FastAPI dependency — extracts and validates the JWT from the request header.

    How it works:
      1. oauth2_scheme reads the Authorization: Bearer <token> header
      2. We decode the token to get the user_id stored in "sub"
      3. We fetch the user from the DB
      4. We return the user — the route handler receives it as a parameter

    If anything fails → 401 Unauthorized is returned automatically.
    """
    from app.services.user_service import get_user_by_id
    import uuid

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = await get_user_by_id(db, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def require_role(*roles: UserRole) -> Callable:
    """
    Dependency factory — returns a dependency that enforces role-based access.

    Usage on a route:
        Depends(require_role(UserRole.instructor))
        Depends(require_role(UserRole.instructor, UserRole.admin))

    How it works:
        1. First calls get_current_user (so auth is always checked first)
        2. Then checks if the user's role is in the allowed list
        3. Raises 403 if not — the route handler never runs

    This is a "factory" — require_role() returns a dependency function.
    Each call to require_role() creates a fresh dependency tailored to those roles.
    """
    async def role_checker(current_user=Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {[r.value for r in roles]}",
            )
        return current_user
    return role_checker
