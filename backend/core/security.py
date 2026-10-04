from datetime import datetime, timedelta
from typing import Any, Union, Optional
import uuid
from jose import jwt, JWTError
import bcrypt
from core.config import settings

# Direct bcrypt usage because passlib 1.7.4 is incompatible with bcrypt 5.0+
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(
    subject: Union[str, Any],
    expires_delta: timedelta = None,
    jti: Optional[str] = None
) -> str:
    """
    Creates a signed JWT access token.
    Includes jti (unique token identifier) for individual revocation support,
    iat (issued-at timestamp), and type='access'.
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    token_jti = jti or uuid.uuid4().hex
    to_encode = {
        "exp": expire,
        "iat": datetime.utcnow(),
        "sub": str(subject),
        "jti": token_jti,
        "type": "access",
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(
    subject: Union[str, Any],
    expires_delta: timedelta = None,
    jti: Optional[str] = None
) -> str:
    """
    Creates a signed JWT refresh token.
    Includes jti, iat, type='refresh', and maintains backward-compatible 'refresh': True.
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    token_jti = jti or uuid.uuid4().hex
    to_encode = {
        "exp": expire,
        "iat": datetime.utcnow(),
        "sub": str(subject),
        "jti": token_jti,
        "type": "refresh",
        "refresh": True,
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    # bcrypt has a 72-byte limit for passwords.
    pwd_bytes = password.encode('utf-8')[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode('utf-8')

def decode_token(token: str) -> Optional[dict]:
    """Decodes token and validates signature and expiration."""
    try:
        decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return decoded_token if decoded_token["exp"] >= datetime.utcnow().timestamp() else None
    except Exception:
        return None

def decode_token_unverified(token: str) -> Optional[dict]:
    """
    Decodes token verifying signature but ignoring expiration.
    Used during logout to extract jti and exp of already expired tokens for safe blacklisting.
    """
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False}
        )
    except Exception:
        return None

