from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.settings.settings import settings


class ForwardHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        """
        Fix URL generation when behind API Gateway.
        Trust X-Forwarded-* headers from Yandex API Gateway.
        """

        forwarded_host = request.headers.get("x-forwarded-host")
        forwarded_proto = request.headers.get(
            "x-forwarded-proto", "https"
        )  # Default to https
        forwarded_prefix = request.headers.get("x-forwarded-prefix", "")

        # Always set scheme if forwarded_proto is present
        if settings.environment == "production":
            if forwarded_proto:
                request.scope["scheme"] = forwarded_proto

            # Set server info if host is forwarded
            if forwarded_host:
                request.scope["server"] = (
                    forwarded_host,
                    443 if forwarded_proto == "https" else 80,
                )

            # Handle path prefix
            if forwarded_prefix:
                request.scope["root_path"] = forwarded_prefix

        return await call_next(request)
