"""
Authentication and authorization module for DegradeWatch backend.
"""
import os
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, status
from app.exceptions import AuthenticationException, AuthorizationException, ValidationException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select

from .models import User, Merchant
from .database import SyncSessionLocal, get_sync_db

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Security scheme
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)


def authenticate_user(db: Session, user_id: str, password: str) -> Optional[User]:
    """Authenticate a user by user_id and password."""
    stmt = select(User).where(User.user_id == user_id)
    user = db.execute(stmt).scalar_one_or_none()
    if not user:
        return False
    if not verify_password(password, user.password_hash):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_db() -> Session:
    """Database session dependency."""
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get the current authenticated user from JWT token."""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise AuthenticationException("Could not validate credentials")
    except JWTError:
        raise AuthenticationException("Could not validate credentials")

    stmt = select(User).where(User.user_id == user_id)
    user = db.execute(stmt).scalar_one_or_none()
    if user is None:
        raise AuthenticationException("Could not validate credentials")
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get the current active user."""
    if not current_user.is_active:
        raise AuthenticationException("Inactive user")
    return current_user


def get_current_merchant_id(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> str:
    """Get the merchant ID for the current user."""
    if current_user.merchant_id is None:
        raise ValidationException("User is not associated with any merchant")

    # Query the merchant to get its merchant_id string
    merchant = db.query(Merchant).filter(Merchant.id == current_user.merchant_id).first()
    if merchant is None:
        raise ValidationException("Merchant not found")
    return merchant.merchant_id


def require_role(required_role: str):
    """Dependency factory for requiring a specific role."""
    def role_checker(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        if not current_user.has_role(required_role):
            raise AuthorizationException(f"Operation requires {required_role} role")
        return current_user
    return role_checker