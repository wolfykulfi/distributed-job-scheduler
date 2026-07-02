import enum
import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin, pg_enum


class LogLevel(str, enum.Enum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class JobLog(UUIDPKMixin, TimestampMixin, Base):
    """Free-form log lines emitted by a handler during a single execution attempt."""

    __tablename__ = "job_logs"

    job_execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    level: Mapped[LogLevel] = mapped_column(pg_enum(LogLevel, "log_level"), nullable=False, default=LogLevel.INFO)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    execution: Mapped["JobExecution"] = relationship(back_populates="logs")
