from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.system import utils
from app.db.dependencies import get_db_session

router = APIRouter()


@router.post("/setup_db/", status_code=status.HTTP_200_OK, summary="Initial setup DB")
async def setup_db(
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    return await utils.setup_db(session)


@router.get("/health/", status_code=status.HTTP_200_OK, tags=["monitoring"])
async def health_check() -> dict[str, str]:
    """Return a simple health payload for readiness probes."""

    return {"status": "ok"}
