import uuid
from typing import Callable

from fastapi import Depends, HTTPException, status

from app.core.security import decode_access_token, oauth2_scheme
from app.infrastructure.cache import is_token_blacklisted
from app.infrastructure.database.unit_of_work import UnitOfWork, get_uow
from app.models.user import User, UserRole
from app.services.user_service import get_user_by_id


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    uow: UnitOfWork = Depends(get_uow),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    jti: str | None = payload.get("jti")
    if jti and await is_token_blacklisted(jti):
        raise credentials_exception

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = await get_user_by_id(uow, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def require_role(*roles: UserRole) -> Callable:
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {[r.value for r in roles]}",
            )
        return current_user

    return role_checker


__all__ = ["get_current_user", "require_role"]
