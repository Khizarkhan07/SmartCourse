import uuid
from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, HTTPException, status

from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import decode_access_token, oauth2_scheme
from app.infrastructure.cache import is_token_blacklisted
from app.models.user import UserRole


@dataclass
class TokenUser:
    """Lightweight user object built from JWT claims — no DB lookup needed."""
    id: uuid.UUID
    role: UserRole
    email: str
    is_active: bool = True


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
) -> TokenUser:
    token = credentials.credentials
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
    role_str: str | None = payload.get("role")
    if not user_id or not role_str:
        raise credentials_exception

    try:
        role = UserRole(role_str)
    except ValueError:
        raise credentials_exception

    return TokenUser(
        id=uuid.UUID(user_id),
        role=role,
        email=payload.get("email", ""),
    )


def require_role(*roles: UserRole) -> Callable:
    async def role_checker(current_user: TokenUser = Depends(get_current_user)) -> TokenUser:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {[r.value for r in roles]}",
            )
        return current_user

    return role_checker


__all__ = ["get_current_user", "require_role", "TokenUser"]
