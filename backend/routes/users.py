from fastapi import APIRouter, Depends, HTTPException
from typing import List
from database.mongodb import get_database
from core.deps import get_current_user, RoleChecker
from schemas.schemas import UserOut, UserCreate, UserUpdate, UserRole
from services.user_agent_team_service import UserService
from services.auth_service import AuthService

router = APIRouter()


@router.get("/", response_model=List[UserOut])
async def list_users(
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    service = UserService(db)
    return await service.get_users()


@router.post("/", response_model=UserOut)
async def create_user(
    user_in: UserCreate,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    auth_service = AuthService(db)
    return await auth_service.register_user(user_in)


@router.get("/me", response_model=UserOut)
async def get_me(current_user=Depends(get_current_user)):
    return current_user


@router.put("/{id}", response_model=UserOut)
async def update_user(
    id: str,
    user_in: UserUpdate,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    service = UserService(db)
    updated = await service.update_user(id, user_in)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return updated


@router.delete("/{id}")
async def delete_user(
    id: str,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    service = UserService(db)
    await service.delete_user(id)
    return {"message": "User deleted"}
