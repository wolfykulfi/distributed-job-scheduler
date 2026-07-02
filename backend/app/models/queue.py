import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class Queue(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "queues"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_queue_project_name"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Higher priority value = drained first. Used as ORDER BY key in the claim query.
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_concurrency: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_retry_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("retry_policies.id", ondelete="SET NULL"), nullable=True
    )

    project: Mapped["Project"] = relationship(back_populates="queues")
    default_retry_policy: Mapped["RetryPolicy | None"] = relationship(back_populates="queues")
    jobs: Mapped[list["Job"]] = relationship(back_populates="queue", cascade="all, delete-orphan")
    scheduled_jobs: Mapped[list["ScheduledJob"]] = relationship(
        back_populates="queue", cascade="all, delete-orphan"
    )
