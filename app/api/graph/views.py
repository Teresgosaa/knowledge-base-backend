from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from app.api.graph.schema import (
    DocIdsResponse,
    EntityTypeMappingResponse,
    EntityTypesResponse,
    GraphDataResponse,
    GraphEdge,
    GraphNode,
    NodeRowResponse,
)
from app.db.user import User
from app.service.neo4j_service import neo4j_service
from app.utils.security import get_current_active_user

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/entity-types", response_model=EntityTypesResponse)
async def get_entity_types(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    from app.service.rag_anything import ENTITY_TYPES

    return EntityTypesResponse(entity_types=list(ENTITY_TYPES.keys()))


@router.get("/entity-type-mapping", response_model=EntityTypeMappingResponse)
async def get_entity_type_mapping(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    from app.service.rag_anything import ENTITY_TYPES

    return EntityTypeMappingResponse(mapping=ENTITY_TYPES)


@router.get("/doc-ids", response_model=DocIdsResponse)
async def get_doc_ids(
    current_user: Annotated[User, Depends(get_current_active_user)],
    entity_type: Optional[str] = Query(None),
):
    doc_ids = neo4j_service.get_doc_ids(entity_type=entity_type)
    return DocIdsResponse(doc_ids=doc_ids)


@router.get("/nodes", response_model=list[NodeRowResponse])
async def get_nodes(
    current_user: Annotated[User, Depends(get_current_active_user)],
    entity_type: Optional[str] = Query(None),
    doc_id: Optional[str] = Query(None),
    entity_value: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    nodes = neo4j_service.get_nodes(
        entity_type=entity_type,
        doc_id=doc_id,
        entity_value=entity_value,
        limit=limit,
        offset=offset,
    )
    return [
        NodeRowResponse(
            id=n["id"],
            entity_types=n.get("entity_types", []),
            properties={k: v for k, v in n.items() if k not in ("id", "entity_types")},
        )
        for n in nodes
    ]


@router.get("/graph", response_model=GraphDataResponse)
async def get_graph(
    current_user: Annotated[User, Depends(get_current_active_user)],
    entity_type: Optional[str] = Query(None),
    doc_id: Optional[str] = Query(None),
    entity_value: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
):
    data = neo4j_service.get_nodes_with_relationships(
        entity_type=entity_type,
        doc_id=doc_id,
        entity_value=entity_value,
        limit=limit,
    )
    return GraphDataResponse(
        nodes=[
            GraphNode(
                id=n["id"],
                labels=[label for label in n["labels"] if label != "base"],
                properties=n["properties"],
            )
            for n in data["nodes"]
        ],
        edges=[
            GraphEdge(
                source=e["source"],
                target=e["target"],
                type=e["type"],
                properties=e["properties"],
            )
            for e in data["edges"]
        ],
    )
