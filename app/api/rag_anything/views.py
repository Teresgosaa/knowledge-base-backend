from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.rag_anything.schema import (
    ProcessRequest,
    ProcessResponse,
    TaskStatusResponse,
)
from app.db.user import User
from app.service.rag_anything import rag_anything_service
from app.utils.security import get_current_active_user

router = APIRouter(prefix="/rag-anything", tags=["rag-anything"])


@router.post("/process", response_model=ProcessResponse)
async def process_folder(
    data: ProcessRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    task_id = await rag_anything_service.start_processing(data.folder_id)
    return ProcessResponse(task_id=task_id)


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    status = rag_anything_service.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    return status
