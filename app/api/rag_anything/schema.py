from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ProcessRequest(BaseModel):
    folder_id: int = Field(..., description="ID of the root folder to process")
    use_vision: bool = Field(default=False, description="Use docling + vision model (slow but processes images)")


class ProcessFromS3Request(BaseModel):
    s3_prefix: str = Field(
        default="",
        description=(
            "S3 key prefix to scan, e.g. 'contracts/'. "
            "Files at <prefix>/<agreement-name>/<file> are grouped by agreement-name. "
            "Leave empty to scan the entire bucket root."
        ),
    )


class ProcessResponse(BaseModel):
    task_id: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    folder_id: Optional[int] = None
    s3_prefix: Optional[str] = None
    total_files: Optional[int] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
