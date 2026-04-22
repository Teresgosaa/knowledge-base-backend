import ssl
import os

ssl._create_default_https_context = ssl._create_unverified_context
os.environ["PYTHONHTTPSVERIFY"] = "0"

import uvicorn

from app.settings.settings import settings


def main() -> None:
    """
    Entrypoint of the application.
    """

    PATH_CERTFILE = "/cert/fullchain.pem"
    PATH_KEYFILE = "/cert/privkey.pem"

    if not os.path.isdir(PATH_CERTFILE) and os.path.exists(PATH_CERTFILE):
        certfile = PATH_CERTFILE
    else:
        certfile = None

    if not os.path.isdir(PATH_KEYFILE) and os.path.exists(PATH_KEYFILE):
        keyfile = PATH_KEYFILE
    else:
        keyfile = None

    uvicorn.run(
        "app.application:get_app",
        workers=settings.workers_count,
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level="info",
        factory=True,
        ssl_certfile=certfile,
        ssl_keyfile=keyfile,
    )


if __name__ == "__main__":
    main()
