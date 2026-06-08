import uuid
from fastapi import APIRouter, Depends, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.user import UserCreate, UserResponse, UserRoleUpdate
from app.services import user_service
from app.auth import require_role
from app.models.user import UserRole
from app.models.user import User
from slowapi.util import get_remote_address

router = APIRouter(prefix="/users", tags=["Users"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/", response_model=UserResponse, status_code=201)
@limiter.limit("5/minute")
async def register_user(request: Request, data: UserCreate, db: AsyncSession = Depends(get_db)):
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
    current_admin: User = Depends(require_role(UserRole.admin, UserRole.instructor)),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
):
    """Return users with pagination. Max 100 per page."""
    return await user_service.list_users(db, limit=limit, offset=offset)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_role(UserRole.admin, UserRole.instructor, UserRole.student)),
):
    """
    Get a single user by ID.
    FastAPI automatically validates that user_id is a valid UUID.
    If not, it returns 422 before your code even runs.
    """
    return await user_service.get_user_by_id(db, user_id)


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    role_update: UserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_role(UserRole.admin)),
):
    """
    Update a user's role. 
    
    **Only admins can access this endpoint.**
    - Requires a valid JWT token with admin role in Authorization header
    - Returns 401 if not authenticated, 403 if not an admin
    - Returns 404 if user not found
    """
    return await user_service.update_user_role(db, user_id, role_update.role)
