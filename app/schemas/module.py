import uuid
from datetime import datetime
from pydantic import BaseModel
from app.schemas.course import CourseResponse


# --- Input Schemas ---

class ModuleCreate(BaseModel):
    """Schema for creating a new module."""
    course_id: uuid.UUID
    title: str
    description: str | None = None
    order: int = 0


class ModuleUpdate(BaseModel):
    """Schema for updating a module — all fields optional."""
    title: str | None = None
    description: str | None = None
    order: int | None = None


# --- Output Schemas ---

class ModuleResponse(BaseModel):
    """Schema for returning module data."""
    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    description: str | None
    order: int
    course: CourseResponse  # nested — returns full course info
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
