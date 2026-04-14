from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from app.db.node_type import NodeType as NodeTypeModel

logger = logging.getLogger(__name__)

_cache: Optional[List[Dict[str, Any]]] = None


def _row_to_dict(row: NodeTypeModel) -> Dict[str, Any]:
    return {
        "id": row.id,
        "alias": row.alias,
        "name": row.name,
        "graph_db_name": row.graph_db_name,
        "layer_type": row.layer_type,
        "color": row.color,
        "is_active": row.is_active,
        "node_definition": row.node_definition or {},
        "russian_names": row.russian_names or [],
    }


async def _load_from_db() -> List[Dict[str, Any]]:
    from app.db.dependencies import get_background_db_session

    async with get_background_db_session() as db:
        result = await db.execute(select(NodeTypeModel).order_by(NodeTypeModel.id))
        rows = result.scalars().all()
    return [_row_to_dict(row) for row in rows]


async def refresh_cache() -> None:
    global _cache
    _cache = await _load_from_db()
    logger.info("Node config cache refreshed from DB (%d items)", len(_cache) if _cache else 0)


def _get_cached() -> List[Dict[str, Any]]:
    if _cache is None:
        logger.warning("Node config cache is empty, call refresh_cache() first")
        return []
    return _cache


def get_entity_types_dict() -> Dict[str, str]:
    result: Dict[str, str] = {}
    for item in _get_cached():
        if not item.get("is_active", True):
            continue
        for rn in item.get("russian_names", []):
            result[rn] = item["graph_db_name"]
    return result


def get_entity_type_keys() -> List[str]:
    return list(get_entity_types_dict().keys())


def get_russian_to_graph_db_map() -> Dict[str, str]:
    return get_entity_types_dict()


def get_semantic_graph_db_names() -> List[str]:
    names: List[str] = []
    seen = set()
    for item in _get_cached():
        if not item.get("is_active", True):
            continue
        if item.get("layer_type") == "semantic":
            gname = item["graph_db_name"]
            if gname not in seen:
                names.append(gname)
                seen.add(gname)
    return names


def get_all_node_types() -> List[Dict[str, Any]]:
    return _get_cached()


def get_active_node_types() -> List[Dict[str, Any]]:
    return [item for item in _get_cached() if item.get("is_active", True)]


def invalidate_cache() -> None:
    global _cache
    _cache = None
