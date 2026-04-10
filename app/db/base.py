from typing import TypeVar

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.sql.sqltypes import DateTime

meta = sa.MetaData()


class Base(DeclarativeBase):
    metadata = meta


class TimestampMixin:
    created_at: Mapped[str] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[str] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AuthorMixin:
    created_by: Mapped[str] = mapped_column(nullable=True)
    updated_by: Mapped[str] = mapped_column(nullable=True)


ModelType = TypeVar("ModelType", bound=Base)
