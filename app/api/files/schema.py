from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class FileCreate(BaseModel):
    description: Optional[str] = None


class FileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class FileResponse(BaseModel):
    id: int
    name: str
    original_name: str
    s3_key: str
    content_type: Optional[str] = None
    size: Optional[int] = None
    description: Optional[str] = None
    folder_id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat() if v else None},
    )


class FileDownloadResponse(BaseModel):
    download_url: str
