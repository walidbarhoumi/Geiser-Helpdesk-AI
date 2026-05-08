import secrets
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.security import verify_password, get_password_hash, create_access_token, create_refresh_token
from schemas.schemas import UserCreate, Token
from models.base import MongoModel
from services.email_service import EmailService

class AuthService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.users

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
        user = await self.collection.find_one({"email": email})
        if not user:
            return # Don't error out to prevent email enumeration
        
        token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(minutes=15)
        
        await self.collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"reset_token": token, "reset_token_expires": expires}}
        )
        
        # Front-end reset URL (assuming it runs on port 5173 for local or relative in prod)
        # Using a relative path for frontend routing
        reset_url = f"http://localhost:5173/reset-password?token={token}"
        EmailService.send_password_reset(email, reset_url)

    async def reset_password(self, token: str, new_password: str):
        user = await self.collection.find_one({
            "reset_token": token,
            "reset_token_expires": {"$gt": datetime.utcnow()}
        })
        if not user:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        hashed_password = get_password_hash(new_password)
        await self.collection.update_one(
            {"_id": user["_id"]},
            {
                "$set": {"hashed_password": hashed_password},
                "$unset": {"reset_token": "", "reset_token_expires": ""}
            }
        )

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
