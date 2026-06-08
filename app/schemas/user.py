import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator
from app.models.user import UserRole


# --- Input Schemas (what the client sends) ---

class UserCreate(BaseModel):
    """Schema for registering a new user."""
    name: str
    email: EmailStr          # Pydantic validates this is a real email format
    password: str
    # Role is NOT accepted during self-registration; all new users start as students.
    # Only admins can promote users via a separate admin endpoint.

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one number")
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter")
        return v


class UserRoleUpdate(BaseModel):
    """Schema for admins to update a user's role."""
    role: UserRole


# --- Output Schemas (what the API returns) ---

class UserResponse(BaseModel):
    """Schema for returning user data — never includes password."""
    id: uuid.UUID
    name: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime

    # This tells Pydantic to read data from SQLAlchemy model attributes
    # Without this, Pydantic wouldn't know how to convert an ORM object to JSON
    model_config = {"from_attributes": True}
