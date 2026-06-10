"""Core security functions: password hashing, JWT tokens, OAuth2 scheme."""

import bcrypt
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer

from app.config import settings

# This tells FastAPI:
# "Protected routes expect a Bearer token at /auth/login"
# It also adds a padlock icon on those routes in /docs so you can test auth there
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(plain_password: str) -> str:
    """Convert a plain text password into a bcrypt hash."""
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check if a plain text password matches a stored hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


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


__all__ = [
    "oauth2_scheme",
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
]
