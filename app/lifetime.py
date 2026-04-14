from contextlib import asynccontextmanager
from functools import partial
from typing import AsyncGenerator

import ujson
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from yarl import URL

from app.db.base import meta
from app.settings.settings import settings

session_factory = None


def _setup_db(app: FastAPI) -> None:
    """
    Creates connection to the database.

    This function creates SQLAlchemy engine instance,
    session_factory for creating sessions
    and stores them in the application's state property.

    :param app: fastAPI application.
    """
    global session_factory

    connection_info = URL.build(
        scheme="postgresql+asyncpg",
        host=settings.db_postgres_host,
        port=settings.db_postgres_port,
        user=settings.db_postgres_user,
        password=settings.db_postgres_password,
        path=f"/{settings.db_postgres_name}",
    )

    engine = create_async_engine(
        str(connection_info),
        echo=True,
        json_serializer=partial(ujson.dumps, ensure_ascii=False),
        pool_pre_ping=True,
    )

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    app.state.db_engine = engine
    app.state.db_session_factory = session_factory


async def _create_tables() -> None:
    """
    Populates tables in the database.
    """
    connection_info = URL.build(
        scheme="postgresql+asyncpg",
        host=settings.db_postgres_host,
        port=settings.db_postgres_port,
        user=settings.db_postgres_user,
        password=settings.db_postgres_password,
        path=f"/{settings.db_postgres_name}",
    )

    engine = create_async_engine(str(connection_info))
    async with engine.begin() as connection:
        await connection.run_sync(meta.create_all)
    await engine.dispose()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan event handler for application startup and shutdown.
    """
    # Startup
    app.middleware_stack = None
    _setup_db(app)
    await _create_tables()
    app.middleware_stack = app.build_middleware_stack()

    from app.service.node_config import refresh_cache
    await refresh_cache()

    yield  # Application runs here

    # Shutdown
    await app.state.db_engine.dispose()
