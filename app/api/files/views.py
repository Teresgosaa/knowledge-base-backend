from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.files.schema import FileDownloadResponse, FileResponse, FileUpdate
from app.db.dependencies import get_db_session
from app.db.user import User
from app.service.file_service import FileService
from app.utils.security import get_current_active_user

router = APIRouter(prefix="/files", tags=["files"])


@router.post(
    "/{folder_id}", response_model=FileResponse, status_code=status.HTTP_201_CREATED
)
async def create_file(
    folder_id: int,
    file: UploadFile,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    content = await file.read()
    service = FileService(db)
    try:
        kb_file = await service.create_file(
            content=content,
            original_name=file.filename or "untitled",
            folder_id=folder_id,
            owner=current_user,
            content_type=file.content_type,
        )
        return kb_file
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{folder_id}", response_model=list[FileResponse])
async def list_files(
    folder_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    service = FileService(db)
    return await service.list_files(folder_id)


@router.get("/detail/{file_id}", response_model=FileResponse)
async def get_file(
    file_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    service = FileService(db)
    kb_file = await service.get_file(file_id)
    if not kb_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )
    return kb_file


@router.get("/download/{file_id}", response_model=FileDownloadResponse)
async def download_file(
    file_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    service = FileService(db)
    url = await service.get_download_url(file_id)
    if not url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )
    return FileDownloadResponse(download_url=url)


@router.patch("/{file_id}", response_model=FileResponse)
async def update_file(
    file_id: int,
    data: FileUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    service = FileService(db)
    kb_file = await service.update_file(
        file_id=file_id,
        name=data.name,
        description=data.description,
    )
    if not kb_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )
    return kb_file


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    service = FileService(db)
    deleted = await service.delete_file(file_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )
