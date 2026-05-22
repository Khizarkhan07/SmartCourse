import uuid
from datetime import datetime
from pydantic import BaseModel
from app.models.course import CourseStatus
from app.schemas.user import UserResponse


# --- Input Schemas ---

class CourseCreate(BaseModel):
    """Schema for creating a new course."""
    title: str
    description: str | None = None  # optional field


class CourseUpdate(BaseModel):
    """Schema for updating an existing course — all fields optional."""
    title: str | None = None
    description: str | None = None
    status: CourseStatus | None = None


# --- Output Schemas ---

class CourseResponse(BaseModel):
    """Schema for returning course data."""
    id: uuid.UUID
    title: str
    description: str | None
    status: CourseStatus
    instructor_id: uuid.UUID
    instructor: UserResponse   # nested — returns full instructor info
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
