# app/template_context.py
from fastapi import Request
from fastapi.templating import Jinja2Templates


def add_template_context(templates: Jinja2Templates):
    """Add custom context to all templates."""

    @staticmethod
    def get_user(request: Request):
        """Get user from request scope."""
        return request.scope.get("user")

    @staticmethod
    def get_user_context(request: Request):
        """Legacy method returning dict with user."""
        return {"user": request.scope.get("user")}

    # Add both methods to templates
    templates.env.globals["get_user"] = get_user
    templates.env.globals["get_user_context"] = get_user_context


# file end
