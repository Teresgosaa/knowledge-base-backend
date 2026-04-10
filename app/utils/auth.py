from typing import Annotated

from fastapi import Cookie, Depends, Header


def get_refresh_token(
    refreshToken_cookie: Annotated[
        str | None,
        Cookie(alias="refreshToken"),
    ] = None,
    refreshToken_header: Annotated[
        str | None,
        Header(alias="X-RefreshToken"),
    ] = None,
) -> str | None:
    """
    Take refresh token from cookie or header.
    """
    return refreshToken_cookie or refreshToken_header


def get_access_token(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> str | None:
    """
    Extract access token from authorization header.
    """
    if authorization is None:
        return None

    _, token = authorization.split(" ")

    return token


RefreshToken = Annotated[str | None, Depends(get_refresh_token)]
AccessToken = Annotated[str | None, Depends(get_access_token)]
