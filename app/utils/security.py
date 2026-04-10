# app/utils/security.py
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db_session
from app.db.user import User
from app.settings.settings import settings

# Password hashing
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__time_cost=2,  # Number of iterations
    argon2__memory_cost=102400,  # Memory usage in KiB
    argon2__parallelism=8,  # Number of parallel threads
    argon2__hash_len=32,  # Output hash length
)

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# JWT settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)

    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})

    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)

    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db_session)
) -> Optional[User]:
    """Get the current authenticated user from JWT token."""
    if not token:
        return None
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id = payload.get("sub")  # Returns str from JWT
        token_type: str = payload.get("type")

        if user_id is None or token_type != "access":
            raise credentials_exception

        # ✅ FIX: Convert user_id to integer for database query
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # Now user_id is int, compatible with User.id column
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


# async def get_current_user(
#     token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db_session)
# ) -> Optional[User]:
#     """Get the current authenticated user from JWT token."""
#     if not token:
#         return None

#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )

#     try:
#         payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
#         user_id: int = payload.get("sub")
#         token_type: str = payload.get("type")

#         if user_id is None or token_type != "access":
#             raise credentials_exception

#     except JWTError:
#         raise credentials_exception

#     result = await db.execute(select(User).where(User.id == user_id))
#     user = result.scalar_one_or_none()

#     if user is None or not user.is_active:
#         raise credentials_exception

#     return user


async def get_current_active_user(
    current_user: Optional[User] = Depends(get_current_user),
) -> User:
    """Get current user and ensure they are active."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Get current user and ensure they are a superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    return current_user


# # Dependency for optional authentication (returns None if not authenticated)
# async def get_optional_current_user(
#     token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db_session)
# ) -> Optional[User]:
#     """Get current user if authenticated, otherwise return None."""
#     if not token:
#         return None

#     try:
#         payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
#         user_id: int = payload.get("sub")
#         token_type: str = payload.get("type")

#         if user_id is None or token_type != "access":
#             return None

#         result = await db.execute(select(User).where(User.id == user_id))
#         user = result.scalar_one_or_none()

#         if user and user.is_active:
#             return user

#     except JWTError:
#         pass

#     return None

# app/utils/security.py - lines ~130-150


async def get_optional_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db_session)
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        token_type: str = payload.get("type")

        if user_id is None or token_type != "access":
            return None

        # ✅ FIX: Same conversion needed here
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return None

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user and user.is_active:
            return user
    except JWTError:
        pass
    return None


# file end
