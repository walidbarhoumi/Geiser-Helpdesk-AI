from fastapi import APIRouter, Depends, HTTPException, status
from database.mongodb import get_database
from services.auth_service import AuthService
from schemas.schemas import (
    UserCreate, Token, UserOut, LoginRequest, LoginResponse, 
    TokenRefresh, LoginResponse2FA, Verify2FARequest, 
    ForgotPasswordRequest, ResetPasswordRequest
)
from typing import Any, Union

router = APIRouter()

@router.post("/register", response_model=UserOut)
async def register(user_in: UserCreate, db=Depends(get_database)) -> Any:
    auth_service = AuthService(db)
    return await auth_service.register_user(user_in)

@router.post("/login", response_model=Union[LoginResponse, LoginResponse2FA])
async def login(login_data: LoginRequest, db=Depends(get_database)) -> Any:
    auth_service = AuthService(db)
    user = await auth_service.authenticate_user(login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    if user.get("two_factor_enabled"):
        await auth_service.initiate_2fa(user)
        return LoginResponse2FA(
            requires_2fa=True,
            email=user["email"],
            message="A verification code has been sent to your email."
        )

    tokens = await auth_service.create_tokens(user["id"])
    return {
        **tokens.dict(),
        "user": user
    }

@router.post("/verify-2fa", response_model=LoginResponse)
async def verify_2fa(data: Verify2FARequest, db=Depends(get_database)) -> Any:
    auth_service = AuthService(db)
    user = await auth_service.verify_2fa(data.email, data.code)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired verification code",
        )
    tokens = await auth_service.create_tokens(user["id"])
    return {
        **tokens.dict(),
        "user": user
    }

@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, db=Depends(get_database)) -> Any:
    auth_service = AuthService(db)
    await auth_service.request_password_reset(data.email)
    return {"message": "If that email is registered, a password reset link has been sent."}

@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, db=Depends(get_database)) -> Any:
    auth_service = AuthService(db)
    await auth_service.reset_password(data.token, data.new_password)
    return {"message": "Password reset successfully. You can now log in."}

@router.post("/logout")
async def logout(db=Depends(get_database)) -> Any:
    auth_service = AuthService(db)
    return await auth_service.logout("")

@router.post("/refresh", response_model=Token)
async def refresh_token(data: TokenRefresh, db=Depends(get_database)) -> Any:
    auth_service = AuthService(db)
    return await auth_service.refresh_access_token(data.refresh_token)
