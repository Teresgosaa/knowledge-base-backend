from typing import Optional

from pydantic import BaseModel


class CriteriaResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    check_prompt: str
    ok_condition: Optional[str] = None
    warning_condition: Optional[str] = None
    reject_condition: Optional[str] = None
    order_num: int
    is_active: bool
    contract_type: str

    model_config = {"from_attributes": True}
