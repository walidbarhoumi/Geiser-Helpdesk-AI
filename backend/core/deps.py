from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
import asyncio
from core.config import settings
from database.mongodb import get_database
from services.user_agent_team_service import UserService
from schemas.schemas import UserRole, AuditEventCategory, AuditSeverity


reusable_oauth2 = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


def get_client_metadata(request: Optional[Request] = None) -> tuple:
    """Extracts client IP address and user-agent string for ISO 27001 audit logging."""
    if request is None:
        return "127.0.0.1", "Internal/Test"
    client_ip = request.headers.get("X-Forwarded-For", "")
    if client_ip:
        client_ip = client_ip.split(",")[0].strip()
    elif request.client and request.client.host:
        client_ip = request.client.host
    else:
        client_ip = "127.0.0.1"

    user_agent = request.headers.get("User-Agent", "Unknown")
    return client_ip, user_agent


async def get_current_user(token: str = Depends(reusable_oauth2), db = Depends(get_database)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    
    user_service = UserService(db)
    user = await user_service.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


class RoleChecker:
    def __init__(self, allowed_roles: list):
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        request: Request = None,
        user = Depends(get_current_user),
        db = Depends(get_database)
    ):
        user_role = user.get("role")
        # Normalize comparison across str and Enum
        role_values = [r.value if hasattr(r, "value") else str(r) for r in self.allowed_roles]
        user_role_val = user_role.value if hasattr(user_role, "value") else str(user_role)

        if user_role_val not in role_values:
            # ISO 27001 Access Control Audit: Log unauthorized privilege attempt
            client_ip, user_agent = get_client_metadata(request)
            path = request.url.path if request else "unknown"
            method = request.method if request else "unknown"

            from services.audit_service import AuditService
            audit_service = AuditService(db)
            asyncio.create_task(
                audit_service.log_event(
                    event_category=AuditEventCategory.ACCESS_CONTROL,
                    event_type="ACCESS_DENIED",
                    severity=AuditSeverity.WARNING,
                    target_resource_type=path,
                    target_resource_id=None,
                    actor_id=str(user.get("id")),
                    actor_email=user.get("email"),
                    actor_name=user.get("full_name") or user.get("email"),
                    actor_role=user_role_val,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    status="DENIED",
                    details={
                        "attempted_path": path,
                        "attempted_method": method,
                        "required_roles": role_values,
                        "user_role": user_role_val,
                    }
                )
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have enough permissions"
            )
        return user
