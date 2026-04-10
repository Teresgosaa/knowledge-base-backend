from typing import Any, Optional

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    labels: list[str]
    properties: dict[str, Any]


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    properties: dict[str, Any]


class GraphDataResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class NodeRowResponse(BaseModel):
    id: str
    entity_types: list[str]
    properties: dict[str, Any]


class EntityTypesResponse(BaseModel):
    entity_types: list[str]


class DocIdsResponse(BaseModel):
    doc_ids: list[str]


class GraphFilterParams(BaseModel):
    entity_type: Optional[str] = None
    doc_id: Optional[str] = None
    entity_value: Optional[str] = None
    limit: int = 100
    offset: int = 0
