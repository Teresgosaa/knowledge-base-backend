from __future__ import annotations

import uuid
from typing import Any, List, Optional

from pydantic import BaseModel


class ValidateRequest(BaseModel):
    document_id: str
    contract_type: str = "transport"


class FindingItem(BaseModel):
    text: str
    section: Optional[str] = None


class CriterionResult(BaseModel):
    criterion_id: int
    criterion_name: str
    status: str  # OK | WARNING | REJECT
    summary: str
    findings: List[FindingItem] = []
    recommendations: List[str] = []


class ValidationReportResponse(BaseModel):
    id: uuid.UUID
    document_id: Optional[str] = None
    bundle: Optional[List[str]] = None
    overall_status: str
    results: Optional[List[Any]] = None
    user_id: Optional[int] = None
    created_at: Any = None

    model_config = {"from_attributes": True}
