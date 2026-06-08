import uuid
from datetime import datetime
from pydantic import BaseModel
from app.models.enrollment import EnrollmentStatus
from app.schemas.user import UserResponse
from app.schemas.course import CourseResponse


# --- Input Schemas ---

class EnrollmentRequest(BaseModel):
    """Schema for enrollment API requests (student inferred from auth token)."""
    course_id: uuid.UUID


class EnrollmentCreate(BaseModel):
    """Schema for creating a new enrollment."""
    student_id: uuid.UUID
    course_id: uuid.UUID


# --- Output Schemas ---

class EnrollmentResponse(BaseModel):
    """Schema for returning enrollment data."""
    id: uuid.UUID
    student_id: uuid.UUID
    course_id: uuid.UUID
    status: EnrollmentStatus
    progress_percentage: int
    student: UserResponse  # nested — returns full student info
    course: CourseResponse  # nested — returns full course info
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
