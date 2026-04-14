from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class NodeTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    graph_db_name: str = Field(..., min_length=1, max_length=255)
    layer_type: str = Field(..., min_length=1, max_length=50)
    color: Optional[str] = None
    is_active: bool = True
    node_definition: Optional[Dict[str, Any]] = None
    russian_names: Optional[List[str]] = []


class NodeTypeUpdate(BaseModel):
    name: Optional[str] = None
    graph_db_name: Optional[str] = None
    layer_type: Optional[str] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None
    node_definition: Optional[Dict[str, Any]] = None
    russian_names: Optional[List[str]] = None


class NodeTypeResponse(BaseModel):
    id: int
    name: str
    graph_db_name: str
    layer_type: str
    color: Optional[str] = None
    is_active: bool
    node_definition: Optional[Dict[str, Any]] = None
    russian_names: Optional[List[str]] = []

    model_config = {"from_attributes": True}


class NodeTypeListResponse(BaseModel):
    items: List[NodeTypeResponse]


class LoadFromJsonRequest(BaseModel):
    json_path: Optional[str] = None


class LoadFromJsonResponse(BaseModel):
    loaded: int
