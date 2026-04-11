from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LayerInfo(BaseModel):
    name: str
    layer_type: str
    description: str
    node_types: List[str]


class PropertyInfo(BaseModel):
    name: str
    type: str
    required: bool = False
    description: str = ""


class NodeTypeResponse(BaseModel):
    node_type: str
    label: str
    layer: str
    description: str
    properties: List[PropertyInfo]
    subtypes: List[str] = []


class RelationshipTypeInfo(BaseModel):
    rel_type: str
    source_types: List[str]
    target_types: List[str]
    description: str
    properties: List[PropertyInfo] = []


class LayeredGraphNode(BaseModel):
    id: str
    uid: str
    labels: List[str]
    properties: Dict[str, Any]


class LayeredGraphEdge(BaseModel):
    source: str
    target: str
    type: str
    properties: Dict[str, Any] = {}


class LayeredGraphDataResponse(BaseModel):
    nodes: List[LayeredGraphNode]
    edges: List[LayeredGraphEdge]


class PartyInfo(BaseModel):
    name: str
    role: str


class DocumentStats(BaseModel):
    clauses: int = 0
    entities: int = 0
    terms: int = 0
    obligations: int = 0
    findings: int = 0


class DocumentOverviewResponse(BaseModel):
    id: str
    uid: str
    doc_id: str
    title: str
    doc_subtype: str
    original_filename: str = ""
    language: str = "ru"
    parties: List[PartyInfo] = []
    stats: DocumentStats = Field(default_factory=DocumentStats)


class LayersListResponse(BaseModel):
    layers: List[LayerInfo]


class NodeTypesResponse(BaseModel):
    node_types: List[NodeTypeResponse]


class RelationshipTypesResponse(BaseModel):
    relationship_types: List[RelationshipTypeInfo]


class DocIdsResponse(BaseModel):
    doc_ids: List[str]


class LayerNodesResponse(BaseModel):
    nodes: List[LayeredGraphNode]


class LayerEdgesResponse(BaseModel):
    edges: List[LayeredGraphEdge]


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query text")
    doc_id: Optional[str] = None
    node_type: Optional[str] = None
    layer: Optional[str] = None
    limit: int = Field(50, ge=1, le=500)


class SearchResponse(BaseModel):
    results: List[LayeredGraphNode]
