from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from app.api.layered_graph.schema import (
    DocIdsResponse,
    DocumentOverviewResponse,
    LayerEdgesResponse,
    LayeredGraphDataResponse,
    LayerNodesResponse,
    LayersListResponse,
    NodeTypesResponse,
    RelationshipTypesResponse,
    SearchRequest,
    SearchResponse,
)
from app.db.user import User
from app.service.layered_graph import layered_graph_service
from app.utils.security import get_current_active_user

router = APIRouter(prefix="/layered-graph", tags=["layered-graph"])


@router.get("/layers", response_model=LayersListResponse)
async def get_layers(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    layers = layered_graph_service.get_layers()
    return LayersListResponse(layers=layers)


@router.get("/node-types", response_model=NodeTypesResponse)
async def get_node_types(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    node_types = layered_graph_service.get_node_types()
    return NodeTypesResponse(node_types=node_types)


@router.get("/relationship-types", response_model=RelationshipTypesResponse)
async def get_relationship_types(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    rel_types = layered_graph_service.get_relationship_types()
    return RelationshipTypesResponse(relationship_types=rel_types)


@router.get("/doc-ids", response_model=DocIdsResponse)
async def get_doc_ids(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    doc_ids = layered_graph_service.get_document_doc_ids()
    return DocIdsResponse(doc_ids=doc_ids)


@router.get("/documents/{doc_id}", response_model=DocumentOverviewResponse)
async def get_document_overview(
    doc_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    overview = layered_graph_service.get_document_overview(doc_id)
    if not overview:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404, detail="Document not found in layered graph"
        )
    return overview


@router.get("/layers/{layer}/nodes", response_model=LayerNodesResponse)
async def get_layer_nodes(
    layer: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    doc_id: Optional[str] = Query(None),
    node_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    nodes = layered_graph_service.get_layer_nodes(
        layer=layer,
        doc_id=doc_id,
        node_type=node_type,
        limit=limit,
        offset=offset,
    )
    return LayerNodesResponse(nodes=nodes)


@router.get("/layers/{layer}/edges", response_model=LayerEdgesResponse)
async def get_layer_edges(
    layer: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    doc_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
):
    edges = layered_graph_service.get_layer_edges(
        layer=layer,
        doc_id=doc_id,
        limit=limit,
    )
    return LayerEdgesResponse(edges=edges)


@router.get("/layers/{layer}/graph", response_model=LayeredGraphDataResponse)
async def get_layer_graph(
    layer: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    doc_id: Optional[str] = Query(None),
    node_type: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
):
    data = layered_graph_service.get_layer_graph(
        layer=layer,
        doc_id=doc_id,
        node_type=node_type,
        limit=limit,
    )
    return LayeredGraphDataResponse(
        nodes=data["nodes"],
        edges=data["edges"],
    )


@router.post("/search", response_model=SearchResponse)
async def search_nodes(
    request: SearchRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    results = layered_graph_service.search_nodes(
        query=request.query,
        doc_id=request.doc_id,
        node_type=request.node_type,
        layer=request.layer,
        limit=request.limit,
    )
    return SearchResponse(results=results)
