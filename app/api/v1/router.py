from fastapi import APIRouter

from . import (
    analytics,
    auth,
    courses,
    enrollments,
    lessons,
    modules,
    operations,
    publishing,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(courses.router)
api_router.include_router(enrollments.router)
api_router.include_router(modules.router)
api_router.include_router(lessons.router)
api_router.include_router(publishing.router)
api_router.include_router(operations.router)
api_router.include_router(analytics.router)
