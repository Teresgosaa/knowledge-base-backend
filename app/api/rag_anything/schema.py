from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ProcessRequest(BaseModel):
    folder_id: int = Field(..., description="ID of the root folder to process")


class ProcessResponse(BaseModel):
    task_id: str


class TaskStatusResponse(BaseModel):
    task_id: str
    folder_id: int
    status: str
    total_files: Optional[int] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
