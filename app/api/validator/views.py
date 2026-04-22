from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.validator.schema import ValidateRequest, ValidationReportResponse
from app.db.dependencies import get_db_session
from app.db.user import User
from app.service.contract_validator_service import ContractValidatorService
from app.utils.security import get_current_active_user

router = APIRouter(prefix="/validator", tags=["validator"])


@router.post("/check", response_model=ValidationReportResponse)
async def validate_contract(
    request: ValidateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Run compliance validation of a contract document against all active criteria."""
    svc = ContractValidatorService(db)
    try:
        report = await svc.validate_contract(
            document_id=request.document_id,
            user_id=current_user.id,
            contract_type=request.contract_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Validation failed: {exc}")
    return report


@router.get("/reports/{report_id}", response_model=ValidationReportResponse)
async def get_report(
    report_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Retrieve a previously generated validation report."""
    svc = ContractValidatorService(db)
    report = await svc.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
