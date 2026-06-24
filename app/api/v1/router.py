from fastapi import APIRouter

from . import (
    enrollments,
    operations,
)

api_router = APIRouter()
api_router.include_router(enrollments.router)
api_router.include_router(operations.router)
