from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.criteria.schema import CriteriaResponse
from app.db.compliance import ComplianceCriteria
from app.db.dependencies import get_db_session
from app.db.user import User
from app.utils.security import get_current_active_user

router = APIRouter(prefix="/criteria", tags=["criteria"])


@router.get("", response_model=List[CriteriaResponse])
async def list_criteria(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    contract_type: Optional[str] = None,
    is_active: Optional[bool] = None,
):
    query = select(ComplianceCriteria).order_by(ComplianceCriteria.order_num)
    if contract_type is not None:
        query = query.where(ComplianceCriteria.contract_type == contract_type)
    if is_active is not None:
        query = query.where(ComplianceCriteria.is_active == is_active)
    result = await db.execute(query)
    return list(result.scalars().all())
