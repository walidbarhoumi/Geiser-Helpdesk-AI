from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from database.mongodb import get_database
from services.auth_service import AuthService
from schemas.schemas import UserCreate, Token, UserOut
from typing import Any

router = APIRouter()

@router.post("/register", response_model=UserOut)
async def register(user_in: UserCreate, db=Depends(get_database)) -> Any:
    auth_service = AuthService(db)
    return await auth_service.register_user(user_in)

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_database)) -> Any:
    auth_service = AuthService(db)
    user = await auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return await auth_service.create_tokens(user["_id"])
