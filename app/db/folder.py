from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.user import User
    from app.db.kb_file import KBFile


class Folder(TimestampMixin, Base):
    __tablename__ = "folders"

    id: Mapped[int] = mapped_column(
        primary_key=True, nullable=False, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("folders.id", ondelete="CASCADE"), nullable=True
    )
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    parent: Mapped[Optional["Folder"]] = relationship(
        "Folder", remote_side=[id], back_populates="children"
    )
    children: Mapped[List["Folder"]] = relationship(
        "Folder", back_populates="parent", cascade="all, delete-orphan"
    )
    owner: Mapped["User"] = relationship("User")
    files: Mapped[List["KBFile"]] = relationship(
        "KBFile", back_populates="folder", cascade="all, delete-orphan"
    )
