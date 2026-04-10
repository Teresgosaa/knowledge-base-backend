from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.folder import Folder
    from app.db.user import User


class KBFile(TimestampMixin, Base):
    __tablename__ = "kb_files"

    id: Mapped[int] = mapped_column(
        primary_key=True, nullable=False, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    folder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("folders.id", ondelete="CASCADE"), nullable=False
    )  # type: ignore[name-defined]
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    folder: Mapped["Folder"] = relationship("Folder", back_populates="files")
    owner: Mapped["User"] = relationship("User")
