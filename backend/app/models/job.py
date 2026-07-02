import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin, pg_enum


class JobType(str, enum.Enum):
    IMMEDIATE = "immediate"
    DELAYED = "delayed"
    SCHEDULED = "scheduled"
    RECURRING_INSTANCE = "recurring_instance"  # spawned by a ScheduledJob firing
    BATCH = "batch"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"          # ready to be claimed now
    SCHEDULED = "scheduled"    # waiting for scheduled_for / next_retry_at
    CLAIMED = "claimed"        # claimed by a worker, not yet executing
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"          # terminal for this attempt, but may still be retried -> SCHEDULED
    DEAD_LETTER = "dead_letter"  # exhausted retries
    CANCELLED = "cancelled"


class Batch(UUIDPKMixin, TimestampMixin, Base):
    """Groups jobs created together in a single bulk-submit call for aggregate tracking."""

    __tablename__ = "batches"

    queue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("queues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    total_jobs: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    jobs: Mapped[list["Job"]] = relationship(back_populates="batch")


class Job(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        # Dedup: at most one non-terminal job per (queue, idempotency_key). Partial index so
        # retried/completed jobs don't block reuse of the same key for a new submission.
        Index(
            "uq_job_idempotency_active",
            "queue_id",
            "idempotency_key",
            unique=True,
            postgresql_where=Column("idempotency_key").isnot(None),
        ),
        # Covers the atomic claim query: WHERE queue_id=? AND status='queued' ORDER BY priority DESC.
        Index("ix_job_claim_lookup", "queue_id", "status", "priority"),
    )

    queue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("queues.id", ondelete="CASCADE"), nullable=False
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batches.id", ondelete="SET NULL"), nullable=True
    )
    scheduled_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scheduled_jobs.id", ondelete="SET NULL"), nullable=True
    )
    retry_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("retry_policies.id", ondelete="SET NULL"), nullable=True
    )
    claimed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workers.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # `name` selects the handler function in the worker's registry (see app/worker/handlers.py)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_type: Mapped[JobType] = mapped_column(pg_enum(JobType, "job_type"), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        pg_enum(JobStatus, "job_status"), nullable=False, default=JobStatus.QUEUED, index=True
    )
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Dedup key, unique per queue when set (see uq_job_idempotency partial index in migration)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)

    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    queue: Mapped["Queue"] = relationship(back_populates="jobs")
    batch: Mapped["Batch | None"] = relationship(back_populates="jobs")
    retry_policy: Mapped["RetryPolicy | None"] = relationship()
    executions: Mapped[list["JobExecution"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobExecution.attempt_number"
    )
