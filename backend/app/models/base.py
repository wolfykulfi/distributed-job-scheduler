import enum
import uuid
from datetime import datetime
from typing import Type

from sqlalchemy import DateTime, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def pg_enum(enum_cls: Type[enum.Enum], name: str) -> SAEnum:
    """Native Postgres enum keyed by the Python enum's `.value` (lowercase), not its `.name`.

    SQLAlchemy's default `Enum()` stores the member *name* (e.g. "RECURRING_INSTANCE"), which
    would leave the DB enum labels inconsistent with the lowercase snake_case values used
    everywhere else (API payloads, filters, docs). `values_callable` makes them match.
    """
    return SAEnum(enum_cls, name=name, values_callable=lambda cls: [e.value for e in cls])


class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
