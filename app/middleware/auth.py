import base64
import json
import logging
from typing import Any, Dict

from fastapi import Request
from jose import JWTError, jwt
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware

from app.db.user import User
from app.settings.settings import settings
from app.utils.security import ALGORITHM

PUBLIC_PATH_PREFIXES = (
    "/login/",
    "/docs",
    "/static",
    "/health.",
)

logger = logging.getLogger(__name__)

if not hasattr(Request, "user"):
    Request.user = property(lambda self: self.scope.get("user"))  # type: ignore


class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        yc_header = request.headers.get("x-yc-apigateway-authorization-context")

        if yc_header:
            try:
                decoded_bytes = base64.b64decode(yc_header)
                yc_context: Dict[str, Any] = json.loads(decoded_bytes.decode("utf-8"))

                login = yc_context.get("login")
                email = yc_context.get("email")
                display_name = yc_context.get("display_name")

                db_session_factory = getattr(
                    request.app.state, "db_session_factory", None
                )
                if db_session_factory is not None:
                    user = None
                    async with db_session_factory() as db:
                        result = await db.execute(
                            select(User).where(User.email == email)
                        )
                        user = result.scalar_one_or_none()

                        if user:
                            if user.is_active:
                                request.scope["user"] = user
                            else:
                                user = None
                        else:
                            user = User(
                                email=email,
                                username=login,
                                full_name=display_name,
                                hashed_password=None,
                                is_active=True,
                                is_superuser=False,
                            )
                            db.add(user)
                            await db.commit()
                            await db.refresh(user)
                            request.scope["user"] = user

                    if user is not None:
                        return await call_next(request)

            except Exception as e:
                print(f"Error decoding or parsing yc_header: {e}")

        if request.url.path.startswith(PUBLIC_PATH_PREFIXES):
            return await call_next(request)

        request.scope["user"] = None
        authorization = request.headers.get("Authorization")
        token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = request.cookies.get("accessToken")
        if token:
            try:
                payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
                user_id = payload.get("sub")
                token_type = payload.get("type")
                if user_id and token_type == "access":
                    db_session_factory = getattr(
                        request.app.state, "db_session_factory", None
                    )
                    if db_session_factory is not None:
                        async with db_session_factory() as db:
                            result = await db.execute(
                                select(User).where(User.id == int(user_id))
                            )
                            user = result.scalar_one_or_none()
                            if user and user.is_active:
                                request.scope["user"] = user
            except (JWTError, ValueError) as exc:
                # Log at debug or warning; do not leak token
                logger.debug("Failed to decode JWT: %s", exc, exc_info=False)

        return await call_next(request)
