import uuid

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_current_user, get_repo, require_role
from models.user import User, UserRole
from repositories.user_repository import UserRepository
from schemas.user import UserCreate, UserResponse, UserRoleUpdate
from services import user_service

router = APIRouter(tags=["Users"])


@router.post("/", response_model=UserResponse, status_code=201)
async def register_user(
    data: UserCreate,
    repo: UserRepository = Depends(get_repo),
):
    return await user_service.create_user(repo, data)


@router.get("/", response_model=list[UserResponse])
async def list_users(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    repo: UserRepository = Depends(get_repo),
    _: User = Depends(require_role(UserRole.admin, UserRole.instructor)),
):
    return await user_service.list_users(repo, limit=limit, offset=offset)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    repo: UserRepository = Depends(get_repo),
    _: User = Depends(get_current_user),
):
    return await user_service.get_user_by_id(repo, user_id)


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    body: UserRoleUpdate,
    repo: UserRepository = Depends(get_repo),
    _: User = Depends(require_role(UserRole.admin)),
):
    return await user_service.update_user_role(repo, user_id, body.role)


@router.delete("/{user_id}", response_model=UserResponse)
async def delete_user(
    user_id: uuid.UUID,
    repo: UserRepository = Depends(get_repo),
    _: User = Depends(require_role(UserRole.admin)),
):
    return await user_service.soft_delete_user(repo, user_id)
