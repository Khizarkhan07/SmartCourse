import uuid
from datetime import datetime

from pydantic import BaseModel


class LessonCreate(BaseModel):
    module_id: uuid.UUID
    title: str
    content: str | None = None
    order: int = 0


class LessonUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    order: int | None = None


class LessonResponse(BaseModel):
    id: uuid.UUID
    module_id: uuid.UUID
    title: str
    content: str | None
    order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
