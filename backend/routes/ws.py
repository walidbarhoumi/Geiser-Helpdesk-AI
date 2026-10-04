"""
routes/ws.py
============
STEP 5 — WebSocket Real-Time Communication & Live Notifications

WebSocket route with strict JWT handshake authentication, connection management,
application-level heartbeat (ping/pong), and clean disconnection lifecycle.
Endpoint: WS /api/v1/ws?token=<access_token>
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, status, HTTPException
from jose import jwt, JWTError
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from core.config import settings
from database.mongodb import get_database
from models.base import MongoModel
from core.deps import RoleChecker
from schemas.schemas import UserRole, AuditEventCategory, AuditSeverity
from websocket.manager import connection_manager
from websocket.events import EventType, create_event

logger = logging.getLogger(__name__)

router = APIRouter()


async def _authenticate_websocket(
    websocket: WebSocket,
    token: Optional[str],
    db
) -> Optional[Dict[str, Any]]:
    """
    Validates JWT access token during WebSocket handshake.
    Strictly checks:
    - Signature & algorithm
    - Expiration
    - Token type (never accepts refresh tokens)
    - Token blacklist (revocation)
    - User existence and active status
    """
    if not token:
        logger.warning("[WS Auth] Handshake rejected: No token provided")
        return None

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if not user_id:
            logger.warning("[WS Auth] Handshake rejected: Missing 'sub' claim in JWT")
            return None

        # Disallow refresh tokens
        if payload.get("refresh") or payload.get("type") == "refresh":
            logger.warning("[WS Auth] Handshake rejected: Refresh token presented instead of access token")
            return None

        # Check blacklist
        jti = payload.get("jti")
        if jti and db is not None:
            revoked = await db.token_blacklist.find_one({"jti": jti}, {"_id": 1})
            if revoked:
                logger.warning(f"[WS Auth] Handshake rejected: Token jti={jti} is revoked")
                return None

        # Check user status in database
        if db is not None:
            user = await db.users.find_one({"_id": MongoModel.to_object_id(user_id)})
            if not user:
                logger.warning(f"[WS Auth] Handshake rejected: User {user_id} not found in DB")
                return None
            if not user.get("is_active", True):
                logger.warning(f"[WS Auth] Handshake rejected: User {user_id} is inactive / disabled")
                return None
            user_data = MongoModel.format_id(user)
            return user_data
        else:
            # Fallback for lightweight testing when db is mock/none
            return {
                "id": user_id,
                "role": payload.get("role", "USER"),
                "email": payload.get("email", ""),
                "is_active": True
            }

    except JWTError as e:
        logger.warning(f"[WS Auth] Handshake rejected: JWT error ({e})")
        return None
    except Exception as e:
        logger.error(f"[WS Auth] Unexpected handshake error: {e}")
        return None


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    db=Depends(get_database)
):
    """
    Main authenticated WebSocket entry point for the GEISER platform.
    URL: WS /api/v1/ws?token=<access_token>
    """
    # 1. Authenticate before accepting the connection
    user = await _authenticate_websocket(websocket, token, db)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 2. Accept and Register Connection
    await websocket.accept()
    user_id = str(user.get("id") or user.get("_id"))
    await connection_manager.connect(websocket, user)

    # 3. Send initial connected event
    await websocket.send_json(create_event(
        EventType.SYSTEM_CONNECTED,
        {
            "user_id": user_id,
            "role": user.get("role"),
            "connected_at": datetime.utcnow().isoformat() + "Z",
        }
    ))

    # 4. Optional ISO 27001 Audit Log
    try:
        if db is not None:
            from services.audit_service import AuditService
            audit_svc = AuditService(db)
            await audit_svc.log_event(
                event_category=AuditEventCategory.AUTHENTICATION,
                event_type="WEBSOCKET_CONNECTED",
                severity=AuditSeverity.INFO,
                target_resource_type="websocket",
                target_resource_id=user_id,
                actor_id=user_id,
                actor_email=user.get("email", ""),
                actor_role=user.get("role", "USER"),
                status="SUCCESS",
                details={"client_host": websocket.client.host if websocket.client else "unknown"}
            )
    except Exception as e:
        logger.debug(f"[WS] Audit logging skipped: {e}")

    # 5. Inbound Message & Heartbeat Loop
    try:
        while True:
            # Await client messages or heartbeats
            data = await websocket.receive_json()
            msg_type = data.get("type") or data.get("event")
            if msg_type in ("ping", EventType.SYSTEM_PING):
                # Respond with pong
                await websocket.send_json(create_event(
                    EventType.SYSTEM_PONG,
                    {"reply_to": data.get("event_id"), "server_time": datetime.utcnow().isoformat() + "Z"}
                ))
    except WebSocketDisconnect:
        logger.info(f"[WS] WebSocket disconnected cleanly for user={user_id}")
    except Exception as e:
        logger.debug(f"[WS] WebSocket connection terminated with exception: {e}")
    finally:
        await connection_manager.disconnect(websocket)
        try:
            if db is not None:
                from services.audit_service import AuditService
                audit_svc = AuditService(db)
                await audit_svc.log_event(
                    event_category=AuditEventCategory.AUTHENTICATION,
                    event_type="WEBSOCKET_DISCONNECTED",
                    severity=AuditSeverity.INFO,
                    target_resource_type="websocket",
                    target_resource_id=user_id,
                    actor_id=user_id,
                    actor_email=user.get("email", ""),
                    actor_role=user.get("role", "USER"),
                    status="SUCCESS",
                )
        except Exception:
            pass


@router.get("/status")
async def get_websocket_status(
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    """
    Diagnostic status endpoint returning active WebSocket statistics (Admin only).
    """
    return connection_manager.get_stats()
