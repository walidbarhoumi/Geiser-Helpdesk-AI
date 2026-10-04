from fastapi import APIRouter, Depends, HTTPException, status, Request
from database.mongodb import get_database
from services.auth_service import AuthService
from core.deps import get_current_user, get_client_metadata
from schemas.schemas import (
    UserCreate, Token, UserOut, LoginRequest, LoginResponse,
    TokenRefresh, LogoutRequest, LoginResponse2FA, Verify2FARequest,
    ForgotPasswordRequest, ResetPasswordRequest,
    TwoFactorStatusOut, TwoFactorEnableConfirm,
    TwoFactorDisableRequest, TwoFactorDisableConfirm
)
from typing import Any, Union, Optional
from core.rate_limit import (
    get_rate_limiter_login,
    get_rate_limiter_2fa,
    get_rate_limiter_password_reset,
)


router = APIRouter()

@router.post("/register", response_model=UserOut)
async def register(user_in: UserCreate, db=Depends(get_database)) -> Any:
    auth_service = AuthService(db)
    return await auth_service.register_user(user_in)

@router.post(
    "/login",
    response_model=Union[LoginResponse, LoginResponse2FA],
    dependencies=[Depends(get_rate_limiter_login())],
)
async def login(login_data: LoginRequest, request: Request, db=Depends(get_database)) -> Any:
    auth_service = AuthService(db)
    client_ip, user_agent = get_client_metadata(request)
    user = await auth_service.authenticate_user(login_data.email, login_data.password, client_ip=client_ip, user_agent=user_agent)
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

@router.post(
    "/verify-2fa",
    response_model=LoginResponse,
    dependencies=[Depends(get_rate_limiter_2fa())],
)
async def verify_2fa(data: Verify2FARequest, request: Request, db=Depends(get_database)) -> Any:
    auth_service = AuthService(db)
    client_ip, user_agent = get_client_metadata(request)
    user = await auth_service.verify_2fa(data.email, data.code, client_ip=client_ip, user_agent=user_agent)
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

@router.post(
    "/forgot-password",
    dependencies=[Depends(get_rate_limiter_password_reset())],
)
async def forgot_password(data: ForgotPasswordRequest, request: Request, db=Depends(get_database)) -> Any:
    auth_service = AuthService(db)
    client_ip, user_agent = get_client_metadata(request)
    await auth_service.request_password_reset(data.email, client_ip=client_ip, user_agent=user_agent)
    return {"message": "If that email is registered, a password reset link has been sent."}

@router.post(
    "/reset-password",
    dependencies=[Depends(get_rate_limiter_password_reset())],
)
async def reset_password(data: ResetPasswordRequest, request: Request, db=Depends(get_database)) -> Any:
    auth_service = AuthService(db)
    client_ip, user_agent = get_client_metadata(request)
    await auth_service.reset_password(data.token, data.new_password, client_ip=client_ip, user_agent=user_agent)
    return {"message": "Password reset successfully. You can now log in."}

@router.post("/logout")
async def logout(
    request: Request,
    logout_data: Optional[LogoutRequest] = None,
    db=Depends(get_database)
) -> Any:
    auth_service = AuthService(db)
    client_ip, user_agent = get_client_metadata(request)

    # Extract Bearer access token from Authorization header if present
    auth_header = request.headers.get("Authorization", "")
    access_token = None
    if auth_header.startswith("Bearer "):
        access_token = auth_header[7:].strip()

    refresh_token = logout_data.refresh_token if logout_data else None

    return await auth_service.logout(
        access_token=access_token,
        refresh_token=refresh_token,
        client_ip=client_ip,
        user_agent=user_agent
    )

@router.post("/refresh", response_model=Token)
async def refresh_token(data: TokenRefresh, request: Request, db=Depends(get_database)) -> Any:
    auth_service = AuthService(db)
    client_ip, user_agent = get_client_metadata(request)
    return await auth_service.refresh_access_token(
        data.refresh_token,
        client_ip=client_ip,
        user_agent=user_agent
    )



# ─────────────────────────────────────────────────────────────────────
# 2FA Management — Profile (authenticated user manages their own 2FA)
# ─────────────────────────────────────────────────────────────────────

@router.get("/2fa/status", response_model=TwoFactorStatusOut)
async def get_2fa_status(
    current_user=Depends(get_current_user),
    db=Depends(get_database)
) -> Any:
    """
    Returns the current 2FA status for the authenticated user.
    Never exposes OTP code, password, or sensitive fields.
    """
    auth_service = AuthService(db)
    return await auth_service.get_2fa_status(current_user["id"])


@router.post(
    "/2fa/enable/request",
    dependencies=[Depends(get_rate_limiter_2fa())],
)
async def request_enable_2fa(
    request: Request,
    current_user=Depends(get_current_user),
    db=Depends(get_database)
) -> Any:
    """
    Step 1 — Sends a 6-digit OTP to the user's registered email to confirm 2FA activation.
    The user must NOT already have 2FA enabled.
    """
    auth_service = AuthService(db)
    client_ip, user_agent = get_client_metadata(request)
    return await auth_service.request_enable_2fa(
        current_user["id"], client_ip=client_ip, user_agent=user_agent
    )


@router.post(
    "/2fa/enable/confirm",
    dependencies=[Depends(get_rate_limiter_2fa())],
)
async def confirm_enable_2fa(
    data: TwoFactorEnableConfirm,
    request: Request,
    current_user=Depends(get_current_user),
    db=Depends(get_database)
) -> Any:
    """
    Step 2 — Validates OTP and enables 2FA.
    Sets two_factor_enabled=True and clears the pending OTP fields.
    """
    auth_service = AuthService(db)
    client_ip, user_agent = get_client_metadata(request)
    return await auth_service.confirm_enable_2fa(
        current_user["id"], data.code, client_ip=client_ip, user_agent=user_agent
    )


@router.post(
    "/2fa/disable/request",
    dependencies=[Depends(get_rate_limiter_2fa())],
)
async def request_disable_2fa(
    data: TwoFactorDisableRequest,
    request: Request,
    current_user=Depends(get_current_user),
    db=Depends(get_database)
) -> Any:
    """
    Step 1 — Verifies current password then sends OTP for 2FA disable confirmation.
    Dual-layer security: password + OTP.
    """
    auth_service = AuthService(db)
    client_ip, user_agent = get_client_metadata(request)
    return await auth_service.request_disable_2fa(
        current_user["id"], data.password, client_ip=client_ip, user_agent=user_agent
    )


@router.post(
    "/2fa/disable/confirm",
    dependencies=[Depends(get_rate_limiter_2fa())],
)
async def confirm_disable_2fa(
    data: TwoFactorDisableConfirm,
    request: Request,
    current_user=Depends(get_current_user),
    db=Depends(get_database)
) -> Any:
    """
    Step 2 — Validates OTP and disables 2FA.
    Sets two_factor_enabled=False and clears the pending OTP fields.
    """
    auth_service = AuthService(db)
    client_ip, user_agent = get_client_metadata(request)
    return await auth_service.confirm_disable_2fa(
        current_user["id"], data.code, client_ip=client_ip, user_agent=user_agent
    )

