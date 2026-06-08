from datetime import date
from pydantic import BaseModel, Field


class EnrollmentTimeSeriesPoint(BaseModel):
    date: date
    enrollments: int


class PopularCoursePoint(BaseModel):
    course_id: str
    title: str
    enrollment_count: int


class AnalyticsOverviewResponse(BaseModel):
    total_students: int
    total_instructors: int
    total_courses_published: int
    new_enrollments_last_30_days: int
    course_completion_rate: float = Field(
        description="Completed enrollments divided by total enrollments (0-1)."
    )
    avg_time_to_complete_days: float
    avg_courses_per_student: float
    failed_workflow_count: int
    most_popular_courses: list[PopularCoursePoint]


class EnrollmentAnalyticsResponse(BaseModel):
    period_days: int
    total_new_enrollments: int
    points: list[EnrollmentTimeSeriesPoint]


class CourseAnalyticsResponse(BaseModel):
    completion_rate: float
    avg_time_to_complete_days: float
    avg_courses_per_student: float
    most_popular_courses: list[PopularCoursePoint]


class WorkflowAnalyticsResponse(BaseModel):
    failed_workflow_count: int
