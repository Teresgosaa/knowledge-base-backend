from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.responses import Response


class JSONException(Exception):
    """
    An JSON exception for short-circuiting responses.
    """

    def __init__(self, status_code: int, content: dict):
        self.status_code = status_code
        self.content = content


def json_exception_handler(request: Request, exc: JSONException) -> Response:
    return JSONResponse(status_code=exc.status_code, content=exc.content)
