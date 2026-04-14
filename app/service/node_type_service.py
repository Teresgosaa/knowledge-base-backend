from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.node_type import NodeType

logger = logging.getLogger(__name__)

_data_dir = Path(__file__).resolve().parent.parent.parent / "data"
_cache: Optional[Dict[str, Any]] = None


class NodeTypeService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_all(self) -> List[NodeType]:
        result = await self._db.execute(select(NodeType).order_by(NodeType.id))
        return list(result.scalars().all())

    async def get_active(self) -> List[NodeType]:
        result = await self._db.execute(select(NodeType).where(NodeType.is_active).order_by(NodeType.id))
        return list(result.scalars().all())

    async def get_by_id(self, node_id: int) -> Optional[NodeType]:
        result = await self._db.execute(select(NodeType).where(NodeType.id == node_id))
        return result.scalar_one_or_none()

    async def get_by_graph_db_name(self, graph_db_name: str) -> Optional[NodeType]:
        result = await self._db.execute(select(NodeType).where(NodeType.graph_db_name == graph_db_name))
        return result.scalar_one_or_none()

    async def create(self, data: Dict[str, Any]) -> NodeType:
        node = NodeType(**data)
        self._db.add(node)
        await self._db.commit()
        await self._db.refresh(node)
        return node

    async def update(self, node_id: int, data: Dict[str, Any]) -> Optional[NodeType]:
        node = await self.get_by_id(node_id)
        if not node:
            return None
        for key, value in data.items():
            setattr(node, key, value)
        await self._db.commit()
        await self._db.refresh(node)
        return node

    async def delete(self, node_id: int) -> bool:
        node = await self.get_by_id(node_id)
        if not node:
            return False
        await self._db.delete(node)
        await self._db.commit()
        return True

    async def get_entity_types_dict(self) -> Dict[str, str]:
        rows = await self.get_active()
        result: Dict[str, str] = {}
        for row in rows:
            if row.node_names:
                for rn in row.node_names:
                    result[rn] = row.graph_db_name
        return result

    async def get_entity_type_keys(self) -> List[str]:
        rows = await self.get_active()
        keys: List[str] = []
        for row in rows:
            if row.node_names:
                keys.extend(row.node_names)
        return keys
