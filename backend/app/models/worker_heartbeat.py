import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class WorkerHeartbeat(UUIDPKMixin, TimestampMixin, Base):
    """Historical ping log, separate from Worker.last_heartbeat_at, for uptime/health graphs."""

    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    active_job_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    worker: Mapped["Worker"] = relationship(back_populates="heartbeats")
