from fastapi import APIRouter

from . import (
    courses,
    enrollments,
    lessons,
    modules,
    operations,
    publishing,
)

api_router = APIRouter()
api_router.include_router(courses.router)
api_router.include_router(enrollments.router)
api_router.include_router(modules.router)
api_router.include_router(lessons.router)
api_router.include_router(publishing.router)
api_router.include_router(operations.router)
