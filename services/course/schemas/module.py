import uuid
from datetime import datetime

from pydantic import BaseModel


class ModuleCreate(BaseModel):
    course_id: uuid.UUID
    title: str
    description: str | None = None
    order: int = 0


class ModuleUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    order: int | None = None


class ModuleResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    description: str | None
    order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
