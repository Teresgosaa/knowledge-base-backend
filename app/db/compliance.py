from __future__ import annotations

import uuid
from typing import Any, List, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, TimestampMixin


class ComplianceCriteria(TimestampMixin, Base):
    __tablename__ = "compliance_criteria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    check_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    ok_condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    warning_condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reject_condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_num: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    contract_type: Mapped[str] = mapped_column(String(100), nullable=False, default="transport")


class ValidationReport(Base):
    __tablename__ = "validation_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    document_id: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    bundle: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    overall_status: Mapped[str] = mapped_column(String(20), nullable=False)
    results: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(
        DateTime, default=func.now(), server_default=func.now(), nullable=False
    )
