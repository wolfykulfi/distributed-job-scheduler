import enum
import uuid

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin, pg_enum


class RetryStrategy(str, enum.Enum):
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


class RetryPolicy(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "retry_policies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    strategy: Mapped[RetryStrategy] = mapped_column(
        pg_enum(RetryStrategy, "retry_strategy"), default=RetryStrategy.EXPONENTIAL, nullable=False
    )
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    base_delay_seconds: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_delay_seconds: Mapped[int] = mapped_column(Integer, default=3600, nullable=False)
    multiplier: Mapped[float] = mapped_column(default=2.0, nullable=False)

    # id kept generic (uuid.UUID) via mixin; type hint below only for clarity in relationships
    queues: Mapped[list["Queue"]] = relationship(back_populates="default_retry_policy")
