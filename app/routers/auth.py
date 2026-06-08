from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.user_service import get_user_by_email
from app.security import verify_password
from app.auth import create_access_token
from app.limiter import limiter

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login")
@limiter.limit("5/minute")   # max 5 login attempts per IP per minute
async def login(
    request: Request,        # required by slowapi to read the IP
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Login and receive a JWT token.
    Rate limited to 5 attempts per minute per IP.
    Exceeding this returns HTTP 429 Too Many Requests.
    """
    user = await get_user_by_email(db, form_data.username)

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
