import uuid
from datetime import datetime
from pydantic import BaseModel
from app.schemas.module import ModuleResponse


# --- Input Schemas ---

class LessonCreate(BaseModel):
    """Schema for creating a new lesson."""
    module_id: uuid.UUID
    title: str
    content: str | None = None
    order: int = 0


class LessonUpdate(BaseModel):
    """Schema for updating a lesson — all fields optional."""
    title: str | None = None
    content: str | None = None
    order: int | None = None


# --- Output Schemas ---

class LessonResponse(BaseModel):
    """Schema for returning lesson data."""
    id: uuid.UUID
    module_id: uuid.UUID
    title: str
    content: str | None
    order: int
    module: ModuleResponse  # nested — returns full module info
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
