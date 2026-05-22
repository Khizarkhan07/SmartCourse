import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.user import UserCreate, UserResponse
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", response_model=UserResponse, status_code=201)
async def register_user(data: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Register a new user.
    FastAPI automatically:
    - Parses the JSON body into a UserCreate object
    - Validates all fields (email format, password length, etc.)
    - Returns 422 with clear error messages if validation fails
    """
    return await user_service.create_user(db, data)


@router.get("/", response_model=list[UserResponse])
async def get_all_users(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100, description="Number of results per page"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
):
    """Return users with pagination. Max 100 per page."""
    return await user_service.list_users(db, limit=limit, offset=offset)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Get a single user by ID.
    FastAPI automatically validates that user_id is a valid UUID.
    If not, it returns 422 before your code even runs.
    """
    return await user_service.get_user_by_id(db, user_id)
