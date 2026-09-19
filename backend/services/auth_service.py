import secrets
import hashlib
import logging
from datetime import datetime, timedelta
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

    async def authenticate_user(self, email: str, password: str):
        user = await self.collection.find_one({"email": email})
        if not user or not verify_password(password, user["hashed_password"]):
            return None
        return MongoModel.format_id(user)

    async def initiate_2fa(self, user: dict):
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        expires = datetime.utcnow() + timedelta(minutes=10)
        await self.collection.update_one(
            {"_id": MongoModel.to_object_id(user["id"])},
            {"$set": {"two_factor_code": code, "two_factor_expires": expires}}
        )
        EmailService.send_2fa_code(user["email"], code)

    async def verify_2fa(self, email: str, code: str):
        user = await self.collection.find_one({
            "email": email,
            "two_factor_code": code,
            "two_factor_expires": {"$gt": datetime.utcnow()}
        })
        if not user:
            return None
        
        # Clear the 2FA code
        await self.collection.update_one(
            {"_id": user["_id"]},
            {"$unset": {"two_factor_code": "", "two_factor_expires": ""}}
        )
        return MongoModel.format_id(user)

    async def request_password_reset(self, email: str):
        # Normalize email
        clean_email = email.strip().lower()
        user = await self.collection.find_one({"email": clean_email})
        if not user:
            logger.info(f"Password reset requested for non-existent email: {clean_email}")
            return  # Anti-enumeration: return quietly without disclosing account presence
        
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

    async def reset_password(self, token: str, new_password: str):
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

        # Mark token as used immediately (single-use enforcement)
        await self.resets.update_one(
            {"_id": reset_doc["_id"]},
            {
                "$set": {
                    "used": True,
                    "used_at": datetime.utcnow()
                }
            }
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

    async def refresh_access_token(self, refresh_token: str):
        from core.security import decode_token
        payload = decode_token(refresh_token)
        if not payload or not payload.get("refresh"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        user_id = payload.get("sub")
        return await self.create_tokens(user_id)

    async def logout(self, token: str):
        return {"message": "Successfully logged out"}
