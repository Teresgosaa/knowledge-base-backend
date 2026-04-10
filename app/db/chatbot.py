from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuthorMixin, Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.user import User


class Message(TimestampMixin, AuthorMixin, Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(nullable=False)
    conversation_id: Mapped[str] = mapped_column(nullable=False)
    message_id: Mapped[str] = mapped_column(nullable=True)
    message: Mapped[str] = mapped_column(nullable=True)
    response: Mapped[str] = mapped_column(nullable=True)
    like: Mapped[bool] = mapped_column(nullable=True, default=None)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="messages")


# end
