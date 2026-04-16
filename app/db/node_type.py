from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class NodeType(TimestampMixin, Base):
    __tablename__ = "node_types"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False, autoincrement=True)
    alias: Mapped[str] = mapped_column(unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    graph_db_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    layer_type: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    node_definition: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    node_names: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True, default=list)
    prompt: Mapped[str] = mapped_column(nullable=True, default=None)
