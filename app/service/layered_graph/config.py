from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from app.db.layer import Layer as LayerModel
from app.db.relationship_type import RelationshipTypeModel

logger = logging.getLogger(__name__)

_layer_cache: Optional[List[Dict[str, Any]]] = None
_rel_type_cache: Optional[List[Dict[str, Any]]] = None


def _layer_row_to_dict(row: LayerModel) -> Dict[str, Any]:
    return {
        "id": row.id,
        "alias": row.alias,
        "name": row.name,
        "layer_type": row.layer_type,
        "description": row.description or "",
        "is_active": row.is_active,
    }


def _rel_row_to_dict(row: RelationshipTypeModel) -> Dict[str, Any]:
    return {
        "id": row.id,
        "alias": row.alias,
        "name": row.name,
        "rel_type": row.rel_type,
        "source_types": row.source_types or [],
        "target_types": row.target_types or [],
        "description": row.description or "",
        "properties": row.properties or [],
        "uses_semantic_source": row.uses_semantic_source,
        "uses_semantic_target": row.uses_semantic_target,
        "is_active": row.is_active,
    }


async def _load_layers() -> List[Dict[str, Any]]:
    from app.db.dependencies import get_background_db_session

    async with get_background_db_session() as db:
        result = await db.execute(select(LayerModel).order_by(LayerModel.id))
        rows = result.scalars().all()
    return [_layer_row_to_dict(row) for row in rows]


async def _load_rel_types() -> List[Dict[str, Any]]:
    from app.db.dependencies import get_background_db_session

    async with get_background_db_session() as db:
        result = await db.execute(select(RelationshipTypeModel).order_by(RelationshipTypeModel.id))
        rows = result.scalars().all()
    return [_rel_row_to_dict(row) for row in rows]


async def refresh_cache() -> None:
    global _layer_cache, _rel_type_cache
    _layer_cache = await _load_layers()
    _rel_type_cache = await _load_rel_types()
    logger.info(
        "Layer graph config cache refreshed from DB (%d layers, %d relationship types)",
        len(_layer_cache) if _layer_cache else 0,
        len(_rel_type_cache) if _rel_type_cache else 0,
    )


def _get_layers() -> List[Dict[str, Any]]:
    if _layer_cache is None:
        logger.warning("Layer config cache is empty, call refresh_cache() first")
        return []
    return _layer_cache


def _get_rel_types() -> List[Dict[str, Any]]:
    if _rel_type_cache is None:
        logger.warning("Relationship type config cache is empty, call refresh_cache() first")
        return []
    return _rel_type_cache


def get_all_layers() -> List[Dict[str, Any]]:
    return _get_layers()


def get_active_layers() -> List[Dict[str, Any]]:
    return [l for l in _get_layers() if l.get("is_active", True)]


def get_layer_by_type(layer_type: str) -> Optional[Dict[str, Any]]:
    for layer in _get_layers():
        if layer["layer_type"] == layer_type and layer.get("is_active", True):
            return layer
    return None


def get_all_relationship_types() -> List[Dict[str, Any]]:
    return _get_rel_types()


def get_active_relationship_types() -> List[Dict[str, Any]]:
    return [r for r in _get_rel_types() if r.get("is_active", True)]


def invalidate_cache() -> None:
    global _layer_cache, _rel_type_cache
    _layer_cache = None
    _rel_type_cache = None
