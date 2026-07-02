import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin, pg_enum


class WorkerStatus(str, enum.Enum):
    ONLINE = "online"
    DRAINING = "draining"   # finishing in-flight jobs before shutdown, claims no new work
    OFFLINE = "offline"


class Worker(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "workers"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[WorkerStatus] = mapped_column(
        pg_enum(WorkerStatus, "worker_status"), nullable=False, default=WorkerStatus.ONLINE, index=True
    )
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="workers")
    heartbeats: Mapped[list["WorkerHeartbeat"]] = relationship(
        back_populates="worker", cascade="all, delete-orphan"
    )
