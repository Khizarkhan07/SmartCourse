import uuid
import bcrypt
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from fastapi.security import HTTPBearer

from app.config import settings

# HTTPBearer: monolith no longer issues tokens — identity-service does.
# Swagger shows "paste your token here" instead of a login form.
# Get a token from localhost:8080/auth/login then paste it in.
oauth2_scheme = HTTPBearer()


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
    to_encode["jti"] = str(uuid.uuid4())  # unique ID per token — used for blacklisting on logout
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
