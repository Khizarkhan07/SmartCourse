from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request

from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies import get_current_user
from app.core.limiter import limiter
from app.core.security import create_access_token, decode_access_token, oauth2_scheme, verify_password
from app.infrastructure.cache import blacklist_token
from app.infrastructure.database.unit_of_work import UnitOfWork, get_uow
from app.models.user import User
from app.services.user_service import get_user_by_email

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login")
@limiter.limit("5/minute")   # max 5 login attempts per IP per minute
async def login(
    request: Request,        # required by slowapi to read the IP
    form_data: OAuth2PasswordRequestForm = Depends(),
    uow: UnitOfWork = Depends(get_uow),
):
    """
    Login and receive a JWT token.
    Rate limited to 5 attempts per minute per IP.
    Exceeding this returns HTTP 429 Too Many Requests.
    """
    user = await get_user_by_email(uow, form_data.username)

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    token = create_access_token(data={
        "sub": str(user.id),
        "role": user.role.value,
    })

    return {"access_token": token, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
):
    """
    Invalidate the current JWT token.
    The token is blacklisted in Redis until it would have naturally expired.
    Any subsequent request using this token receives 401.
    """
    payload = decode_access_token(token)
    if payload:
        jti: str | None = payload.get("jti")
        exp: int | None = payload.get("exp")
        if jti and exp:
            ttl = int(exp - datetime.now(timezone.utc).timestamp())
            if ttl > 0:
                await blacklist_token(jti, ttl)
