"""Atomic job-claiming logic used by the worker /poll endpoint.

The core reliability guarantee: two workers polling concurrently must never claim the same job.
This is achieved with `SELECT ... FOR UPDATE SKIP LOCKED` -- each concurrent transaction locks
only the rows it intends to claim and skips any row already locked by another in-flight poll,
rather than blocking on it. The UPDATE that flips status -> CLAIMED happens in the same
transaction as the SELECT, so the row is claimed before the lock is released at commit.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.job import Job, JobStatus
from app.models.job_dependency import JobDependency
from app.models.queue import Queue
from app.models.worker import Worker
from app.services.notify_service import notify_job_event

_ACTIVE_STATUSES = (JobStatus.CLAIMED, JobStatus.RUNNING)


async def _active_count(db: AsyncSession, queue_id) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.queue_id == queue_id, Job.status.in_(_ACTIVE_STATUSES))
    ) or 0


async def claim_jobs_for_worker(db: AsyncSession, worker: Worker, max_jobs: int) -> list[Job]:
    now = datetime.now(timezone.utc)

    queues = await db.scalars(
        select(Queue)
        .where(Queue.project_id == worker.project_id, Queue.is_paused.is_(False))
        .order_by(Queue.priority.desc())
    )

    claimed: list[Job] = []
    for queue in queues:
        remaining = max_jobs - len(claimed)
        if remaining <= 0:
            break

        active = await _active_count(db, queue.id)
        available = queue.max_concurrency - active
        if available <= 0:
            continue

        take = min(available, remaining)

        # A job with any dependency not yet 'completed' is not claimable -- correlated subquery,
        # not a status field, so workflow deps compose cleanly with retries/rescheduling without
        # a new job status.
        dep_job = aliased(Job)
        has_unmet_dependency = (
            select(JobDependency.id)
            .join(dep_job, dep_job.id == JobDependency.depends_on_job_id)
            .where(JobDependency.job_id == Job.id, dep_job.status != JobStatus.COMPLETED)
            .exists()
        )

        # Eligible: QUEUED jobs, or SCHEDULED/FAILED-retry jobs whose wake time has arrived.
        candidate_stmt = (
            select(Job.id)
            .where(
                Job.queue_id == queue.id,
                (Job.status == JobStatus.QUEUED)
                | (
                    (Job.status == JobStatus.SCHEDULED)
                    & (Job.scheduled_for.is_(None) | (Job.scheduled_for <= now))
                    & (Job.next_retry_at.is_(None) | (Job.next_retry_at <= now))
                ),
                ~has_unmet_dependency,
            )
            .order_by(Job.priority.desc(), Job.created_at.asc())
            .limit(take)
            .with_for_update(skip_locked=True)
        )
        job_ids = list(await db.scalars(candidate_stmt))
        if not job_ids:
            continue

        await db.execute(
            update(Job)
            .where(Job.id.in_(job_ids))
            .values(status=JobStatus.CLAIMED, claimed_by=worker.id, claimed_at=now)
        )
        for job_id in job_ids:
            await notify_job_event(db, queue.id, job_id, JobStatus.CLAIMED.value)

        rows = await db.scalars(select(Job).where(Job.id.in_(job_ids)))
        claimed.extend(rows)

    if claimed:
        await db.commit()
        for job in claimed:
            await db.refresh(job)
    return claimed
