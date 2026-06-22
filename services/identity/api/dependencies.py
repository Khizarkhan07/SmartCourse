import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from core.security import decode_access_token
from database import AsyncSessionLocal
from infrastructure.cache import is_token_blacklisted
from models.user import User, UserRole
from repositories.user_repository import UserRepository

# OAuth2PasswordBearer lets Swagger show a username/password login form
# that hits /auth/login directly — correct for the service that issues tokens.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_repo() -> UserRepository:
    async with AsyncSessionLocal() as session:
        yield UserRepository(session)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    repo: UserRepository = Depends(get_repo),
) -> User:
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    jti = payload.get("jti")
    if jti and await is_token_blacklisted(jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    user = await repo.get_by_id(uuid.UUID(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_role(*roles: UserRole):
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return current_user
    return _check
