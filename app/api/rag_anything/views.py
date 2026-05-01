from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.rag_anything.schema import (
    ProcessFromS3Request,
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
    task_id = await rag_anything_service.start_processing(data.folder_id, use_vision=data.use_vision)
    return ProcessResponse(task_id=task_id)


@router.post("/process-from-s3", response_model=ProcessResponse)
async def process_from_s3(
    data: ProcessFromS3Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Index files already stored in Yandex Cloud S3.

    Files are discovered by listing the given *s3_prefix*.
    Each immediate sub-folder under the prefix is treated as a separate
    agreement/contract (its name becomes the ``doc_id`` in the graph).
    Files located directly under the prefix (without a sub-folder) are
    grouped under the synthetic agreement name ``_root``.
    """
    task_id = await rag_anything_service.start_processing_from_s3(data.s3_prefix)
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
