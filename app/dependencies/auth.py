# app/dependencies/auth.py
from typing import Optional

from fastapi import Depends, Request

from app.db.user import User


async def get_current_user_from_request(request: Request) -> Optional[User]:
    """Get current user from request scope (set by middleware)."""
    return request.scope.get("user")


# Dependency for routes that need user

CurrentUser = Optional[User]

# Dependency for routes that need user
CurrentUser = Depends(get_current_user_from_request)


async def require_active_user(
    user: Optional[User] = Depends(get_current_user_from_request),
) -> User:
    """Require an active authenticated user."""
    if not user or not user.is_active:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


async def require_superuser(user: User = Depends(require_active_user)) -> User:
    """Require superuser privileges."""
    if not user.is_superuser:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return user
