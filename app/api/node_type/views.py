from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.node_type.schema import (
    NodeTypeCreate,
    NodeTypeListResponse,
    NodeTypeResponse,
    NodeTypeUpdate,
)
from app.db.dependencies import get_db_session
from app.db.user import User
from app.service.node_type_service import NodeTypeService
from app.utils.security import get_current_active_user

router = APIRouter(prefix="/node-types", tags=["node-types"])


@router.get("", response_model=NodeTypeListResponse)
async def list_node_types(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    svc = NodeTypeService(db)
    items = await svc.get_all()
    return NodeTypeListResponse(items=items)  # type: ignore


@router.get("/{node_id}", response_model=NodeTypeResponse)
async def get_node_type(
    node_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    svc = NodeTypeService(db)
    node = await svc.get_by_id(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Semantic node type not found")
    return node


@router.post("", response_model=NodeTypeResponse, status_code=201)
async def create_node_type(
    data: NodeTypeCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    svc = NodeTypeService(db)
    node = await svc.create(data.model_dump())
    return node


@router.patch("/{node_id}", response_model=NodeTypeResponse)
async def update_node_type(
    node_id: int,
    data: NodeTypeUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    svc = NodeTypeService(db)
    updated = await svc.update(node_id, data.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Semantic node type not found")
    return updated


@router.delete("/{node_id}", status_code=204)
async def delete_node_type(
    node_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    svc = NodeTypeService(db)
    deleted = await svc.delete(node_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Semantic node type not found")
