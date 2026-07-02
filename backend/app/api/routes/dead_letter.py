import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_queue_role
from app.core.exceptions import ConflictError, NotFoundError
from app.database import get_db
from app.models.dead_letter import DeadLetterJob
from app.models.job import Job, JobStatus
from app.models.organization import OrgRole
from app.models.user import User
from app.schemas.job import DeadLetterResponse, JobResponse

router = APIRouter(tags=["dead-letter"])


@router.get("/api/v1/queues/{queue_id}/dead-letter", response_model=list[DeadLetterResponse])
async def list_dead_letter_jobs(
    queue_id: uuid.UUID,
    resolved: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DeadLetterJob]:
    await require_queue_role(queue_id, OrgRole.MEMBER, db, user)
    result = await db.scalars(
        select(DeadLetterJob)
        .where(DeadLetterJob.queue_id == queue_id, DeadLetterJob.resolved == resolved)
        .order_by(DeadLetterJob.moved_at.desc())
    )
    return list(result)


@router.post("/api/v1/dead-letter/{dlq_id}/retry", response_model=JobResponse)
async def retry_dead_letter_job(
    dlq_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Job:
    """Re-queues the original job with a fresh attempt budget and marks the DLQ entry resolved."""
    dlq_entry = await db.get(DeadLetterJob, dlq_id)
    if dlq_entry is None:
        raise NotFoundError("Dead letter entry not found")
    await require_queue_role(dlq_entry.queue_id, OrgRole.ADMIN, db, user)
    if dlq_entry.resolved:
        raise ConflictError("This dead letter entry was already retried")

    job = await db.get(Job, dlq_entry.job_id)
    if job is None:
        raise NotFoundError("Original job no longer exists")

    job.status = JobStatus.QUEUED
    job.attempt_count = 0
    job.next_retry_at = None
    dlq_entry.resolved = True
    dlq_entry.resolved_at = datetime.now(timezone.utc)
    dlq_entry.resolved_by = user.id

    await db.commit()
    await db.refresh(job)
    return job
