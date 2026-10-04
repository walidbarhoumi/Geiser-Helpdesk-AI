import secrets
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.config import settings
from core.security import verify_password, get_password_hash, create_access_token, create_refresh_token
from schemas.schemas import UserCreate, Token
from models.base import MongoModel
from services.email_service import EmailService

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.users
        self.resets = db.password_resets
        self.token_blacklist = db.token_blacklist

    async def register_user(self, user_in: UserCreate):
        existing_user = await self.collection.find_one({"email": user_in.email})
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )

        user_dict = user_in.dict()
        user_dict["hashed_password"] = get_password_hash(user_dict.pop("password"))
        user_dict["created_at"] = datetime.utcnow()
        user_dict["is_active"] = True
        user_dict["two_factor_enabled"] = False

        result = await self.collection.insert_one(user_dict)
        user_dict["_id"] = result.inserted_id
        return MongoModel.format_id(user_dict)

    async def authenticate_user(self, email: str, password: str, client_ip: str = "127.0.0.1", user_agent: str = "Unknown"):
        from services.audit_service import AuditService
        from schemas.schemas import AuditEventCategory, AuditSeverity
        audit_svc = AuditService(self.db)
        clean_identifier = (email or "").strip()

        # 1. Active Directory / LDAP Authentication (if enabled)
        if settings.LDAP_ENABLED:
            from services.ldap_service import LdapService
            ldap_svc = LdapService()
            success, ldap_info, err_msg = await ldap_svc.authenticate_user(clean_identifier, password)

            if success and ldap_info:
                # Synchronize user into local MongoDB
                user = await ldap_svc.sync_user_to_db(ldap_info, self.db)

                if not user.get("is_active", True):
                    await audit_svc.log_event(
                        event_category=AuditEventCategory.AUTH,
                        event_type="LDAP_LOGIN_FAILURE",
                        severity=AuditSeverity.WARNING,
                        target_resource_type="auth_session",
                        target_resource_id=str(user.get("id")),
                        actor_id=str(user.get("id")),
                        actor_email=user.get("email"),
                        actor_role=user.get("role"),
                        client_ip=client_ip,
                        user_agent=user_agent,
                        status="FAILURE",
                        details={"reason": "Compte LDAP désactivé"}
                    )
                    return None

                # ISO 27001 Security Audit: Log successful LDAP login
                user_role = user.get("role", "USER")
                if hasattr(user_role, "value"):
                    user_role = user_role.value

                await audit_svc.log_event(
                    event_category=AuditEventCategory.AUTH,
                    event_type="LDAP_LOGIN_SUCCESS",
                    severity=AuditSeverity.INFO,
                    target_resource_type="auth_session",
                    target_resource_id=str(user.get("id")),
                    actor_id=str(user.get("id")),
                    actor_email=user.get("email"),
                    actor_name=user.get("full_name") or user.get("email"),
                    actor_role=user_role,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    status="SUCCESS",
                    details={
                        "auth_provider": "ldap",
                        "ldap_username": ldap_info.get("username"),
                        "2fa_required": bool(user.get("two_factor_enabled"))
                    }
                )
                return MongoModel.format_id(user)

            elif err_msg == "Invalid credentials":
                # User found in LDAP directory but supplied an incorrect password.
                # Strict fallback: do NOT try local password verification for directory users.
                await audit_svc.log_event(
                    event_category=AuditEventCategory.AUTH,
                    event_type="LDAP_LOGIN_FAILURE",
                    severity=AuditSeverity.WARNING,
                    target_resource_type="auth_session",
                    target_resource_id=None,
                    actor_email=clean_identifier,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    status="FAILURE",
                    details={"reason": "Identifiants LDAP incorrects", "auth_provider": "ldap"}
                )
                return None

            else:
                # Connection error or user not found in directory
                if err_msg and "connection failure" in str(err_msg).lower():
                    await audit_svc.log_event(
                        event_category=AuditEventCategory.AUTH,
                        event_type="LDAP_CONNECTION_ERROR",
                        severity=AuditSeverity.ERROR,
                        target_resource_type="auth_session",
                        target_resource_id=None,
                        actor_email=clean_identifier,
                        client_ip=client_ip,
                        user_agent=user_agent,
                        status="FAILURE",
                        details={"error": str(err_msg)}
                    )
                # Fall through to check local users (e.g. emergency local admin accounts)

        # 2. Local Database Authentication
        user = await self.collection.find_one({
            "$or": [
                {"email": clean_identifier.lower()},
                {"ldap_username": clean_identifier.lower()}
            ]
        })

        # Security check: if account is managed by LDAP, never allow local password login
        if user and user.get("auth_provider") == "ldap" and settings.LDAP_ENABLED:
            await audit_svc.log_event(
                event_category=AuditEventCategory.AUTH,
                event_type="AUTH_LOGIN_FAILURE",
                severity=AuditSeverity.WARNING,
                target_resource_type="auth_session",
                target_resource_id=str(user["_id"]),
                actor_id=str(user["_id"]),
                actor_email=clean_identifier,
                actor_role=user.get("role"),
                client_ip=client_ip,
                user_agent=user_agent,
                status="FAILURE",
                details={"reason": "Compte géré par Active Directory - mot de passe local interdit"}
            )
            return None

        if not user or not verify_password(password, user.get("hashed_password", "")):
            # ISO 27001 Security Audit: Log failed login attempt
            await audit_svc.log_event(
                event_category=AuditEventCategory.AUTH,
                event_type="AUTH_LOGIN_FAILURE",
                severity=AuditSeverity.WARNING,
                target_resource_type="auth_session",
                target_resource_id=None,
                actor_id=str(user["_id"]) if user else None,
                actor_email=clean_identifier,
                actor_role=user.get("role") if user else None,
                client_ip=client_ip,
                user_agent=user_agent,
                status="FAILURE",
                details={"reason": "Incorrect email or password"}
            )
            return None

        # ISO 27001 Security Audit: Log successful login
        user_role = user.get("role", "USER")
        if hasattr(user_role, "value"):
            user_role = user_role.value

        await audit_svc.log_event(
            event_category=AuditEventCategory.AUTH,
            event_type="AUTH_LOGIN_SUCCESS",
            severity=AuditSeverity.INFO,
            target_resource_type="auth_session",
            target_resource_id=str(user["_id"]),
            actor_id=str(user["_id"]),
            actor_email=user.get("email"),
            actor_name=user.get("full_name") or user.get("email"),
            actor_role=user_role,
            client_ip=client_ip,
            user_agent=user_agent,
            status="SUCCESS",
            details={
                "auth_provider": user.get("auth_provider", "local"),
                "2fa_required": bool(user.get("two_factor_enabled"))
            }
        )
        return MongoModel.format_id(user)

    async def initiate_2fa(self, user: dict):
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        expires = datetime.utcnow() + timedelta(minutes=10)
        await self.collection.update_one(
            {"_id": MongoModel.to_object_id(user["id"])},
            {"$set": {"two_factor_code": code, "two_factor_expires": expires}}
        )
        EmailService.send_2fa_code(user["email"], code)

    async def verify_2fa(self, email: str, code: str, client_ip: str = "127.0.0.1", user_agent: str = "Unknown"):
        from services.audit_service import AuditService
        from schemas.schemas import AuditEventCategory, AuditSeverity
        audit_svc = AuditService(self.db)

        user = await self.collection.find_one({
            "email": email,
            "two_factor_code": code,
            "two_factor_expires": {"$gt": datetime.utcnow()}
        })
        if not user:
            await audit_svc.log_event(
                event_category=AuditEventCategory.AUTH,
                event_type="AUTH_2FA_FAILURE",
                severity=AuditSeverity.WARNING,
                target_resource_type="2fa_session",
                target_resource_id=None,
                actor_email=email,
                client_ip=client_ip,
                user_agent=user_agent,
                status="FAILURE",
                details={"reason": "Invalid or expired verification code"}
            )
            return None
        
        # Clear the 2FA code
        await self.collection.update_one(
            {"_id": user["_id"]},
            {"$unset": {"two_factor_code": "", "two_factor_expires": ""}}
        )

        user_role = user.get("role", "USER")
        if hasattr(user_role, "value"):
            user_role = user_role.value

        await audit_svc.log_event(
            event_category=AuditEventCategory.AUTH,
            event_type="AUTH_2FA_SUCCESS",
            severity=AuditSeverity.INFO,
            target_resource_type="2fa_session",
            target_resource_id=str(user["_id"]),
            actor_id=str(user["_id"]),
            actor_email=user.get("email"),
            actor_name=user.get("full_name") or user.get("email"),
            actor_role=user_role,
            client_ip=client_ip,
            user_agent=user_agent,
            status="SUCCESS",
            details={"method": "OTP_EMAIL"}
        )
        return MongoModel.format_id(user)

    async def request_password_reset(self, email: str, client_ip: str = "127.0.0.1", user_agent: str = "Unknown"):
        from services.audit_service import AuditService
        from schemas.schemas import AuditEventCategory, AuditSeverity
        audit_svc = AuditService(self.db)

        # Normalize email
        clean_email = email.strip().lower()
        user = await self.collection.find_one({"email": clean_email})
        if not user:
            logger.info(f"Password reset requested for non-existent email: {clean_email}")
            return  # Anti-enumeration: return quietly without disclosing account presence
        
        if user.get("auth_provider") == "ldap":
            logger.info(f"Password reset requested for LDAP user: {clean_email} - ignored (directory managed)")
            return  # Anti-enumeration: do not issue local token for directory-managed users
        
        # Invalidate any prior unused tokens for this user
        await self.resets.update_many(
            {"user_id": user["_id"], "used": False},
            {"$set": {"used": True, "invalidated_at": datetime.utcnow()}}
        )

        # Generate cryptographically secure random token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        expires_at = datetime.utcnow() + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)
        
        # Store only hashed token in dedicated collection
        await self.resets.insert_one({
            "user_id": user["_id"],
            "email": clean_email,
            "token_hash": token_hash,
            "expires_at": expires_at,
            "used": False,
            "created_at": datetime.utcnow()
        })
        
        # Build frontend reset URL using configured FRONTEND_URL
        base_url = settings.FRONTEND_URL.rstrip('/')
        reset_url = f"{base_url}/reset-password?token={raw_token}"
        EmailService.send_password_reset(clean_email, reset_url)
        logger.info(f"Password reset link generated and dispatched for user_id={user['_id']}")

        await audit_svc.log_event(
            event_category=AuditEventCategory.AUTH,
            event_type="PASSWORD_RESET_REQUESTED",
            severity=AuditSeverity.INFO,
            target_resource_type="password_reset",
            target_resource_id=str(user["_id"]),
            actor_id=str(user["_id"]),
            actor_email=clean_email,
            client_ip=client_ip,
            user_agent=user_agent,
            status="SUCCESS",
            details={"dispatched_via": "EMAIL"}
        )

    async def reset_password(self, token: str, new_password: str, client_ip: str = "127.0.0.1", user_agent: str = "Unknown"):
        from services.audit_service import AuditService
        from schemas.schemas import AuditEventCategory, AuditSeverity
        audit_svc = AuditService(self.db)

        clean_token = token.strip()
        if not clean_token:
            raise HTTPException(status_code=400, detail="Invalid or missing reset token")

        if len(new_password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")

        # Hash incoming raw token with SHA-256 to compare against stored hash
        token_hash = hashlib.sha256(clean_token.encode('utf-8')).hexdigest()
        
        reset_doc = await self.resets.find_one({
            "token_hash": token_hash,
            "used": False,
            "expires_at": {"$gt": datetime.utcnow()}
        })

        if not reset_doc:
            await audit_svc.log_event(
                event_category=AuditEventCategory.AUTH,
                event_type="PASSWORD_RESET_FAILURE",
                severity=AuditSeverity.WARNING,
                target_resource_type="password_reset",
                target_resource_id=None,
                client_ip=client_ip,
                user_agent=user_agent,
                status="FAILURE",
                details={"reason": "Invalid or expired reset token"}
            )
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        # Hash new password with existing bcrypt system
        hashed_password = get_password_hash(new_password)
        
        # Update user password in users collection
        user_oid = reset_doc["user_id"]
        await self.collection.update_one(
            {"_id": user_oid},
            {
                "$set": {
                    "hashed_password": hashed_password,
                    "password_changed_at": datetime.utcnow()
                },
                "$unset": {"reset_token": "", "reset_token_expires": ""}
            }
        )

        # Mark token as used
        await self.resets.update_one(
            {"_id": reset_doc["_id"]},
            {"$set": {"used": True, "used_at": datetime.utcnow()}}
        )

        await audit_svc.log_event(
            event_category=AuditEventCategory.AUTH,
            event_type="PASSWORD_RESET_SUCCESS",
            severity=AuditSeverity.INFO,
            target_resource_type="user",
            target_resource_id=str(user_oid),
            actor_id=str(user_oid),
            actor_email=reset_doc.get("email"),
            client_ip=client_ip,
            user_agent=user_agent,
            status="SUCCESS",
            details={"password_updated": True}
        )

        logger.info(f"Password successfully reset for user_id={user_oid}")


    async def create_tokens(self, user_id: str):
        access_token = create_access_token(subject=user_id)
        refresh_token = create_refresh_token(subject=user_id)
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )

    async def revoke_token(
        self,
        token: str,
        token_type: str = "access",
        reason: str = "logout",
        user_id: Optional[str] = None
    ) -> Optional[dict]:
        """
        Revokes a JWT token (access or refresh) by storing its jti and expiration in MongoDB.
        Uses update_one with upsert=True to guarantee idempotence.
        Accepts expired tokens safely via unverified decode so that logout with an expired token
        can still record its revocation if jti is present.
        """
        from core.security import decode_token_unverified
        payload = decode_token_unverified(token)
        if not payload:
            return None

        jti = payload.get("jti")
        if not jti:
            return None  # Legacy token without jti cannot be tracked individually in blacklist

        sub = payload.get("sub") or user_id
        exp_ts = payload.get("exp")
        if exp_ts:
            expires_at = datetime.utcfromtimestamp(exp_ts)
        else:
            expires_at = datetime.utcnow() + timedelta(hours=1)

        doc = {
            "jti": jti,
            "user_id": str(sub) if sub else None,
            "token_type": token_type,
            "expires_at": expires_at,
            "revoked_at": datetime.utcnow(),
            "reason": reason,
        }

        await self.token_blacklist.update_one(
            {"jti": jti},
            {"$setOnInsert": doc},
            upsert=True
        )
        return doc

    async def is_token_revoked(self, jti: str) -> bool:
        """Checks if a token JTI has been revoked in the blacklist."""
        if not jti:
            return False
        revoked = await self.token_blacklist.find_one({"jti": jti}, {"_id": 1})
        return revoked is not None

    async def refresh_access_token(
        self,
        refresh_token: str,
        client_ip: str = "127.0.0.1",
        user_agent: str = "Unknown"
    ):
        from core.security import decode_token
        from services.audit_service import AuditService
        from schemas.schemas import AuditEventCategory, AuditSeverity
        audit_svc = AuditService(self.db)

        payload = decode_token(refresh_token)
        if not payload or not payload.get("refresh"):
            await audit_svc.log_event(
                event_category=AuditEventCategory.AUTH,
                event_type="AUTH_REFRESH_FAILURE",
                severity=AuditSeverity.WARNING,
                target_resource_type="auth_token",
                client_ip=client_ip,
                user_agent=user_agent,
                status="FAILURE",
                details={"reason": "Invalid or expired refresh token"}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        # Check if refresh token has been revoked
        jti = payload.get("jti")
        if jti and await self.is_token_revoked(jti):
            await audit_svc.log_event(
                event_category=AuditEventCategory.AUTH,
                event_type="AUTH_REFRESH_FAILURE",
                severity=AuditSeverity.WARNING,
                target_resource_type="auth_token",
                actor_id=payload.get("sub"),
                client_ip=client_ip,
                user_agent=user_agent,
                status="FAILURE",
                details={"reason": "Revoked refresh token reuse attempt", "jti": jti}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )

        user_id = payload.get("sub")
        tokens = await self.create_tokens(user_id)

        await audit_svc.log_event(
            event_category=AuditEventCategory.AUTH,
            event_type="AUTH_REFRESH_SUCCESS",
            severity=AuditSeverity.INFO,
            target_resource_type="auth_token",
            actor_id=user_id,
            client_ip=client_ip,
            user_agent=user_agent,
            status="SUCCESS",
            details={"refreshed_user_id": user_id}
        )
        return tokens

    async def logout(
        self,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        client_ip: str = "127.0.0.1",
        user_agent: str = "Unknown"
    ) -> dict:
        """
        Revokes the caller's access token and/or refresh token.
        Idempotent: revoking an already revoked token returns success without error.
        Logs an ISO 27001 audit event for the logout.
        """
        from services.audit_service import AuditService
        from schemas.schemas import AuditEventCategory, AuditSeverity
        from core.security import decode_token_unverified
        audit_svc = AuditService(self.db)

        if not access_token and not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        actor_id = None
        actor_email = None
        actor_role = None
        revoked_access_jti = None
        revoked_refresh_jti = None

        # 1. Process and revoke access token if provided
        if access_token:
            payload = decode_token_unverified(access_token)
            if payload is None:
                # If an explicit access token was provided but is completely unparseable (bad signature/malformed)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
            actor_id = payload.get("sub")
            revoked_doc = await self.revoke_token(access_token, token_type="access", reason="logout", user_id=actor_id)
            if revoked_doc:
                revoked_access_jti = revoked_doc["jti"]

        # 2. Process and revoke refresh token if provided
        if refresh_token:
            payload = decode_token_unverified(refresh_token)
            if payload is not None:
                rf_sub = payload.get("sub")
                if not actor_id:
                    actor_id = rf_sub
                revoked_doc = await self.revoke_token(refresh_token, token_type="refresh", reason="logout", user_id=rf_sub)
                if revoked_doc:
                    revoked_refresh_jti = revoked_doc["jti"]

        # Lookup user for rich audit log
        if actor_id:
            try:
                user = await self.collection.find_one({"_id": MongoModel.to_object_id(actor_id)})
                if user:
                    actor_email = user.get("email")
                    actor_role = user.get("role")
            except Exception:
                pass

        # 3. Log ISO 27001 Security Audit Event
        await audit_svc.log_event(
            event_category=AuditEventCategory.AUTH,
            event_type="AUTH_LOGOUT",
            severity=AuditSeverity.INFO,
            target_resource_type="auth_session",
            target_resource_id=actor_id,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_role=actor_role,
            client_ip=client_ip,
            user_agent=user_agent,
            status="SUCCESS",
            details={
                "access_token_jti_revoked": revoked_access_jti,
                "refresh_token_jti_revoked": revoked_refresh_jti,
            }
        )

        return {"message": "Successfully logged out"}


    # ──────────────────────────────────────────────────────────────
    # 2FA Management from Profile
    # ──────────────────────────────────────────────────────────────

    async def get_2fa_status(self, user_id: str) -> dict:
        """Returns the current 2FA status for the authenticated user."""
        user = await self.collection.find_one({"_id": MongoModel.to_object_id(user_id)})
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return {
            "enabled": bool(user.get("two_factor_enabled", False)),
            "method": "email"
        }

    async def request_enable_2fa(
        self,
        user_id: str,
        client_ip: str = "127.0.0.1",
        user_agent: str = "Unknown"
    ) -> dict:
        """
        Step 1 — Enable 2FA: sends a 6-digit OTP to the user's email.
        Guards: user must NOT already have 2FA enabled.
        The OTP is stored with a purpose tag (enable_2fa) to prevent cross-flow reuse.
        """
        from services.audit_service import AuditService
        from schemas.schemas import AuditEventCategory, AuditSeverity
        audit_svc = AuditService(self.db)

        user = await self.collection.find_one({"_id": MongoModel.to_object_id(user_id)})
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if user.get("two_factor_enabled"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Two-factor authentication is already enabled"
            )

        # Generate OTP — same mechanism as login 2FA
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        expires = datetime.utcnow() + timedelta(minutes=10)

        await self.collection.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "pending_2fa_code": code,
                "pending_2fa_expires": expires,
                "pending_2fa_purpose": "enable"
            }}
        )

        EmailService.send_2fa_code(user["email"], code)

        await audit_svc.log_event(
            event_category=AuditEventCategory.AUTH,
            event_type="AUTH_2FA_ENABLE_REQUESTED",
            severity=AuditSeverity.INFO,
            target_resource_type="user_2fa",
            target_resource_id=str(user["_id"]),
            actor_id=str(user["_id"]),
            actor_email=user.get("email"),
            actor_name=user.get("full_name") or user.get("email"),
            actor_role=str(user.get("role", "USER")),
            client_ip=client_ip,
            user_agent=user_agent,
            status="PENDING",
            details={"action": "enable_2fa_otp_sent"}
        )
        return {"message": "A verification code has been sent to your email. Enter it to activate 2FA."}

    async def confirm_enable_2fa(
        self,
        user_id: str,
        code: str,
        client_ip: str = "127.0.0.1",
        user_agent: str = "Unknown"
    ) -> dict:
        """
        Step 2 — Enable 2FA: validates the OTP and sets two_factor_enabled=True.
        OTP is invalidated after one use regardless of success/failure after max attempts.
        """
        from services.audit_service import AuditService
        from schemas.schemas import AuditEventCategory, AuditSeverity
        audit_svc = AuditService(self.db)

        user = await self.collection.find_one({"_id": MongoModel.to_object_id(user_id)})
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if user.get("two_factor_enabled"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Two-factor authentication is already enabled"
            )

        # Validate OTP — check code, purpose, and expiry
        stored_code = user.get("pending_2fa_code")
        stored_expires = user.get("pending_2fa_expires")
        stored_purpose = user.get("pending_2fa_purpose")

        if (
            not stored_code
            or stored_purpose != "enable"
            or not stored_expires
            or stored_expires < datetime.utcnow()
            or not secrets.compare_digest(stored_code, code)
        ):
            await audit_svc.log_event(
                event_category=AuditEventCategory.AUTH,
                event_type="AUTH_2FA_ENABLE_FAILURE",
                severity=AuditSeverity.WARNING,
                target_resource_type="user_2fa",
                target_resource_id=str(user["_id"]),
                actor_id=str(user["_id"]),
                actor_email=user.get("email"),
                actor_role=str(user.get("role", "USER")),
                client_ip=client_ip,
                user_agent=user_agent,
                status="FAILURE",
                details={"reason": "Invalid or expired OTP for 2FA activation"}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired verification code"
            )

        # OTP valid — activate 2FA and clear pending fields
        await self.collection.update_one(
            {"_id": user["_id"]},
            {
                "$set": {"two_factor_enabled": True},
                "$unset": {
                    "pending_2fa_code": "",
                    "pending_2fa_expires": "",
                    "pending_2fa_purpose": ""
                }
            }
        )

        await audit_svc.log_event(
            event_category=AuditEventCategory.AUTH,
            event_type="AUTH_2FA_ENABLED",
            severity=AuditSeverity.INFO,
            target_resource_type="user_2fa",
            target_resource_id=str(user["_id"]),
            actor_id=str(user["_id"]),
            actor_email=user.get("email"),
            actor_name=user.get("full_name") or user.get("email"),
            actor_role=str(user.get("role", "USER")),
            client_ip=client_ip,
            user_agent=user_agent,
            status="SUCCESS",
            details={"method": "OTP_EMAIL"}
        )
        return {"message": "Two-factor authentication has been successfully enabled.", "enabled": True}

    async def request_disable_2fa(
        self,
        user_id: str,
        password: str,
        client_ip: str = "127.0.0.1",
        user_agent: str = "Unknown"
    ) -> dict:
        """
        Step 1 — Disable 2FA: verifies current password then sends OTP.
        Dual verification: password + OTP email.
        """
        from services.audit_service import AuditService
        from schemas.schemas import AuditEventCategory, AuditSeverity
        audit_svc = AuditService(self.db)

        user = await self.collection.find_one({"_id": MongoModel.to_object_id(user_id)})
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if not user.get("two_factor_enabled"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Two-factor authentication is not enabled"
            )

        # Verify current password first
        if not verify_password(password, user.get("hashed_password", "")):
            await audit_svc.log_event(
                event_category=AuditEventCategory.AUTH,
                event_type="AUTH_2FA_DISABLE_FAILURE",
                severity=AuditSeverity.WARNING,
                target_resource_type="user_2fa",
                target_resource_id=str(user["_id"]),
                actor_id=str(user["_id"]),
                actor_email=user.get("email"),
                actor_role=str(user.get("role", "USER")),
                client_ip=client_ip,
                user_agent=user_agent,
                status="FAILURE",
                details={"reason": "Incorrect password during 2FA disable request"}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect password"
            )

        # Password OK — send OTP for second confirmation
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        expires = datetime.utcnow() + timedelta(minutes=10)

        await self.collection.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "pending_2fa_code": code,
                "pending_2fa_expires": expires,
                "pending_2fa_purpose": "disable"
            }}
        )

        EmailService.send_2fa_code(user["email"], code)

        await audit_svc.log_event(
            event_category=AuditEventCategory.AUTH,
            event_type="AUTH_2FA_DISABLE_REQUESTED",
            severity=AuditSeverity.INFO,
            target_resource_type="user_2fa",
            target_resource_id=str(user["_id"]),
            actor_id=str(user["_id"]),
            actor_email=user.get("email"),
            actor_name=user.get("full_name") or user.get("email"),
            actor_role=str(user.get("role", "USER")),
            client_ip=client_ip,
            user_agent=user_agent,
            status="PENDING",
            details={"action": "disable_2fa_otp_sent"}
        )
        return {"message": "Password verified. A confirmation code has been sent to your email."}

    async def confirm_disable_2fa(
        self,
        user_id: str,
        code: str,
        client_ip: str = "127.0.0.1",
        user_agent: str = "Unknown"
    ) -> dict:
        """
        Step 2 — Disable 2FA: validates OTP then sets two_factor_enabled=False.
        """
        from services.audit_service import AuditService
        from schemas.schemas import AuditEventCategory, AuditSeverity
        audit_svc = AuditService(self.db)

        user = await self.collection.find_one({"_id": MongoModel.to_object_id(user_id)})
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if not user.get("two_factor_enabled"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Two-factor authentication is not enabled"
            )

        # Validate OTP — must have purpose=disable
        stored_code = user.get("pending_2fa_code")
        stored_expires = user.get("pending_2fa_expires")
        stored_purpose = user.get("pending_2fa_purpose")

        if (
            not stored_code
            or stored_purpose != "disable"
            or not stored_expires
            or stored_expires < datetime.utcnow()
            or not secrets.compare_digest(stored_code, code)
        ):
            await audit_svc.log_event(
                event_category=AuditEventCategory.AUTH,
                event_type="AUTH_2FA_DISABLE_FAILURE",
                severity=AuditSeverity.WARNING,
                target_resource_type="user_2fa",
                target_resource_id=str(user["_id"]),
                actor_id=str(user["_id"]),
                actor_email=user.get("email"),
                actor_role=str(user.get("role", "USER")),
                client_ip=client_ip,
                user_agent=user_agent,
                status="FAILURE",
                details={"reason": "Invalid or expired OTP for 2FA disable confirmation"}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired verification code"
            )

        # OTP valid — disable 2FA and clear pending fields
        await self.collection.update_one(
            {"_id": user["_id"]},
            {
                "$set": {"two_factor_enabled": False},
                "$unset": {
                    "pending_2fa_code": "",
                    "pending_2fa_expires": "",
                    "pending_2fa_purpose": ""
                }
            }
        )

        await audit_svc.log_event(
            event_category=AuditEventCategory.AUTH,
            event_type="AUTH_2FA_DISABLED",
            severity=AuditSeverity.WARNING,
            target_resource_type="user_2fa",
            target_resource_id=str(user["_id"]),
            actor_id=str(user["_id"]),
            actor_email=user.get("email"),
            actor_name=user.get("full_name") or user.get("email"),
            actor_role=str(user.get("role", "USER")),
            client_ip=client_ip,
            user_agent=user_agent,
            status="SUCCESS",
            details={"method": "OTP_EMAIL"}
        )
        return {"message": "Two-factor authentication has been disabled.", "enabled": False}

