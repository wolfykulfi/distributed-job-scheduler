"""Fires due `ScheduledJob` (cron) definitions into new `Job` rows.

Note: delayed/one-off scheduled jobs and retry backoff don't need a promotion step here --
claim_service.py's claim query already selects SCHEDULED jobs directly once `scheduled_for` /
`next_retry_at` has passed. This loop only handles recurring cron *firing*, which is a
fundamentally different operation (one definition spawns many Job instances over time).

Runs as a first-party control-plane process with direct DB access (unlike workers, which are
treated as an external fleet authenticating over REST -- see docs/DESIGN_DECISIONS.md).
`FOR UPDATE SKIP LOCKED` keeps firing safe even if more than one scheduler replica is running.
"""

from datetime import datetime, timezone

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus, JobType
from app.models.scheduled_job import ScheduledJob


async def fire_due_scheduled_jobs(db: AsyncSession) -> int:
    now = datetime.now(timezone.utc)

    due_ids = list(
        await db.scalars(
            select(ScheduledJob.id)
            .where(ScheduledJob.is_active.is_(True), ScheduledJob.next_run_at <= now)
            .with_for_update(skip_locked=True)
        )
    )
    if not due_ids:
        return 0

    scheduled_jobs = list(await db.scalars(select(ScheduledJob).where(ScheduledJob.id.in_(due_ids))))
    for sj in scheduled_jobs:
        db.add(
            Job(
                queue_id=sj.queue_id,
                scheduled_job_id=sj.id,
                name=sj.name,
                job_type=JobType.RECURRING_INSTANCE,
                status=JobStatus.QUEUED,
                payload=sj.payload,
                retry_policy_id=sj.retry_policy_id,
            )
        )
        sj.last_run_at = now
        sj.next_run_at = croniter(sj.cron_expression, now).get_next(datetime)

    await db.commit()
    return len(scheduled_jobs)
