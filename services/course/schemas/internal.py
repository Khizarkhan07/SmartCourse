import uuid
from pydantic import BaseModel


class LessonInternalResponse(BaseModel):
    id: uuid.UUID
    module_id: uuid.UUID
    course_id: uuid.UUID


class LessonCountResponse(BaseModel):
    course_id: uuid.UUID
    total_lessons: int
