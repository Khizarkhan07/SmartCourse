import uuid
from datetime import datetime

from pydantic import BaseModel

from models.course import CourseStatus


class CourseCreate(BaseModel):
    title: str
    description: str | None = None


class CourseUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: CourseStatus | None = None


class CourseResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    status: CourseStatus
    instructor_id: uuid.UUID
    instructor_name: str | None = None   # from instructor_profiles read model
    instructor_email: str | None = None  # None until first user.profile_updated event arrives
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
