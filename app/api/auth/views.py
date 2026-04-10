# app/api/auth/views.py
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import schema
from app.db.dependencies import get_db_session
from app.db.user import User
from app.settings.settings import settings
from app.utils.auth import RefreshToken
from app.utils.security import (
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    get_current_active_user,
    get_current_superuser,
    get_password_hash,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register/", response_model=schema.UserResponse)
async def register(
    user_data: schema.UserCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Register a new user."""
    # Check if user exists
    result = await db.execute(
        select(User).where((User.username == user_data.username) | (User.email == user_data.email))
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        if existing_user.username == user_data.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )
        if existing_user.email == user_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    # Create new user
    hashed_password = get_password_hash(user_data.password)

    db_user = User(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        hashed_password=hashed_password,
        is_active=True,
        is_superuser=False,
    )

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    return db_user


@router.post("/login/", response_model=schema.Token)
async def login(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Login with username/email and password."""
    # Check if user exists (by username or email)
    result = await db.execute(
        select(User).where((User.username == form_data.username) | (User.email == form_data.username))
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    # Update last login
    # user.last_login = datetime.now().isoformat()
    # await db.commit()

    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    # Set refresh token as HTTP-only cookie
    response.set_cookie(
        key="refreshToken",
        value=refresh_token,
        httponly=True,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        secure=settings.environment == "production",
        samesite="lax",
        path="/api/auth/refresh/",
    )

    # ALSO set access token as HTTP-only cookie for web pages
    response.set_cookie(
        key="accessToken",
        value=access_token,
        httponly=True,
        max_age=30 * 60,  # 30 minutes
        secure=settings.environment == "production",
        samesite="lax",
        path="/",  # Available for all paths
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh/", response_model=schema.Token)
async def refresh_token(
    response: Response,
    refresh_token: RefreshToken,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Get new access token using refresh token."""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    try:
        payload = jwt.decode(refresh_token, settings.secret_key, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        token_type = payload.get("type")

        if user_id is None or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Check if user exists
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Create new tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})

    # Set new refresh token as HTTP-only cookie
    response.set_cookie(
        key="refreshToken",
        value=new_refresh_token,
        httponly=True,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        secure=settings.environment == "production",
        samesite="lax",
        path="/api/auth/refresh/",
    )

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


@router.post("/logout/")
async def logout(response: Response):
    """Logout user by clearing refresh token cookie."""
    response.delete_cookie(
        key="accessToken",
        path="/",
    )
    response.delete_cookie(
        key="refreshToken",
        path="/api/auth/refresh/",
    )

    return {"message": "Successfully logged out"}


@router.get("/me/", response_model=schema.UserResponse)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get current user information."""
    return current_user


@router.put("/me/", response_model=schema.UserResponse)
async def update_current_user(
    user_update: schema.UserUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Update current user information."""
    if user_update.email and user_update.email != current_user.email:
        # Check if email is already taken
        result = await db.execute(select(User).where(User.email == user_update.email))
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        current_user.email = user_update.email

    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name

    if user_update.password:
        current_user.hashed_password = get_password_hash(user_update.password)

    await db.commit()
    await db.refresh(current_user)

    return current_user


@router.post("/change_password/")
async def change_password(
    password_data: schema.ChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Change user password."""
    if not verify_password(password_data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect old password",
        )

    current_user.hashed_password = get_password_hash(password_data.new_password)
    await db.commit()

    return {"message": "Password changed successfully"}


# Admin endpoints
@router.get("/users/", response_model=list[schema.UserResponse])
async def get_users(
    current_user: Annotated[User, Depends(get_current_superuser)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    skip: int = 0,
    limit: int = 100,
):
    """Get all users (admin only)."""
    result = await db.execute(select(User).offset(skip).limit(limit))
    users = result.scalars().all()
    return users


@router.put("/users/{user_id}/toggle_active/", response_model=schema.UserResponse)
async def toggle_user_active(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_superuser)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Toggle user active status (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.is_active = not user.is_active
    await db.commit()
    await db.refresh(user)

    return user


# file end
