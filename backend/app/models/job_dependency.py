import uuid

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class JobDependency(UUIDPKMixin, TimestampMixin, Base):
    """Edge in a job dependency graph: `job_id` cannot be claimed until `depends_on_job_id`
    reaches `completed`. Scoped to jobs within the same queue -- see claim_service.py for the
    eligibility check and DESIGN_DECISIONS.md for why cross-queue deps aren't allowed."""

    __tablename__ = "job_dependencies"
    __table_args__ = (
        UniqueConstraint("job_id", "depends_on_job_id", name="uq_job_dependency"),
        CheckConstraint("job_id != depends_on_job_id", name="ck_job_dependency_not_self"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    depends_on_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
