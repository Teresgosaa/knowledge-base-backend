from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class RelationshipTypeModel(TimestampMixin, Base):
    __tablename__ = "relationship_types"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False, autoincrement=True)
    alias: Mapped[str] = mapped_column(unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rel_type: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    source_types: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True, default=list)
    target_types: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True, default=list)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    properties: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSONB, nullable=True, default=list)
    uses_semantic_source: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    uses_semantic_target: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
