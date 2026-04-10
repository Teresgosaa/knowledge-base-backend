from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.folders.schema import (
    FolderCreate,
    FolderDetailResponse,
    FolderResponse,
    FolderUpdate,
)
from app.db.dependencies import get_db_session
from app.db.user import User
from app.service.folder_service import FolderService
from app.utils.security import get_current_active_user

router = APIRouter(prefix="/folders", tags=["folders"])


@router.post("/", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    data: FolderCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    service = FolderService(db)
    try:
        folder = await service.create_folder(
            name=data.name,
            owner=current_user,
            parent_id=data.parent_id,
            description=data.description,
        )
        return folder
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=list[FolderDetailResponse])
async def list_folders(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    parent_id: int | None = None,
):
    service = FolderService(db)
    folders = await service.list_folders(owner=current_user, parent_id=parent_id)
    return folders


@router.get("/{folder_id}", response_model=FolderDetailResponse)
async def get_folder(
    folder_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    service = FolderService(db)
    folder = await service.get_folder(folder_id)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found"
        )
    return folder


@router.patch("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: int,
    data: FolderUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    service = FolderService(db)
    folder = await service.update_folder(
        folder_id=folder_id,
        name=data.name,
        description=data.description,
    )
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found"
        )
    return folder


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    service = FolderService(db)
    deleted = await service.delete_folder(folder_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found"
        )
