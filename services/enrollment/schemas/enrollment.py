import uuid
from datetime import datetime

from pydantic import BaseModel

from models.enrollment import EnrollmentStatus


class EnrollmentRequest(BaseModel):
    course_id: uuid.UUID


class EnrollmentCreate(BaseModel):
    student_id: uuid.UUID
    course_id: uuid.UUID



class EnrollmentResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    course_id: uuid.UUID
    status: EnrollmentStatus
    progress_percentage: int
    enrolled_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EnrollmentProgressResponse(BaseModel):
    enrollment_id: uuid.UUID
    student_id: uuid.UUID
    course_id: uuid.UUID
    progress_percentage: int
    completed_lessons: int
    total_lessons: int
    enrollment_status: EnrollmentStatus
