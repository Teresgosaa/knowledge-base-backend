import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, UJSONResponse

from app.api.router import router
from app.exceptions import JSONException, json_exception_handler
from app.lifetime import lifespan
from app.middleware.auth import AuthenticationMiddleware
from app.middleware.forwarded_headers import ForwardHeadersMiddleware
from app.settings.settings import settings


def get_app() -> FastAPI:
    """
    Get FastAPI application.

    This is the main constructor of an application.
    """
    app = FastAPI(title="app", default_response_class=UJSONResponse, lifespan=lifespan)

    # Middlewares
    app.add_middleware(ForwardHeadersMiddleware)
    app.add_middleware(AuthenticationMiddleware)

    # # Mount static files directory
    # app.mount("/static", StaticFiles(directory="app/static"), name="static")

    # # For jinja2
    # templates = Jinja2Templates(directory="app/templates")
    # templates.env.filters["tojson"] = json.dumps
    # add_template_context(templates)  # Add this line
    # app.state.templates = templates

    @app.middleware("http")
    async def log_middleware(request: Request, call_next):
        print(request.method, request.url)

        if request.path_params:
            print("Path parameters:", request.path_params)

        if body := await request.body():
            print("Body:", body)

        if request.query_params:
            print("Query parameters:")
            print(request.query_params)

        response = await call_next(request)

        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        exc_str = f"{exc}".replace("\n", " ").replace("   ", " ")
        logging.error(f"{request}: {exc_str}")
        content = {"status_code": 10422, "message": exc_str, "data": None}
        return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_hosts + settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(JSONException, json_exception_handler)  # type: ignore

    app.include_router(router=router)

    # register_startup_event(app)
    # register_shutdown_event(app)

    return app


# end
