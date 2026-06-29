import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.dependencies import get_repo
from repositories.user_repository import UserRepository

router = APIRouter(prefix="/internal", tags=["Internal"])


class UserInternalResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str


@router.get("/users/{user_id}", response_model=UserInternalResponse)
async def get_user_internal(
    user_id: uuid.UUID,
    repo: UserRepository = Depends(get_repo),
):
    """Service-to-service: fetch user name + email by ID (no auth required)."""
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserInternalResponse(id=user.id, name=user.name, email=user.email)
