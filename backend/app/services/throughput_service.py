"""Time-bucketed throughput for the dashboard's throughput/health chart.

Bucketing is done in Python rather than SQL (e.g. Postgres date_trunc) because arbitrary bucket
widths (5-minute, 15-minute, ...) don't map onto date_trunc's fixed units without a more complex
epoch-floor expression -- for the data volumes a dashboard like this deals with, doing it in
Python is simpler and just as fast. A larger deployment computing this over millions of rows
would want the aggregation pushed into SQL.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dead_letter import DeadLetterJob
from app.models.job import Job, JobStatus


async def get_throughput(
    db: AsyncSession, queue_id: uuid.UUID, window_minutes: int = 60, bucket_minutes: int = 5
) -> dict:
    now = datetime.now(timezone.utc)
    since = now - timedelta(minutes=window_minutes)
    num_buckets = max(1, window_minutes // bucket_minutes)

    completed_times = list(
        await db.scalars(
            select(Job.completed_at).where(
                Job.queue_id == queue_id, Job.status == JobStatus.COMPLETED, Job.completed_at >= since
            )
        )
    )
    failed_times = list(
        await db.scalars(
            select(DeadLetterJob.moved_at).where(DeadLetterJob.queue_id == queue_id, DeadLetterJob.moved_at >= since)
        )
    )

    buckets = []
    for i in range(num_buckets):
        bucket_start = since + timedelta(minutes=i * bucket_minutes)
        bucket_end = bucket_start + timedelta(minutes=bucket_minutes)
        completed = sum(1 for t in completed_times if bucket_start <= t < bucket_end)
        failed = sum(1 for t in failed_times if bucket_start <= t < bucket_end)
        buckets.append({"bucket_start": bucket_start, "completed": completed, "failed": failed})

    total_completed = len(completed_times)
    total_failed = len(failed_times)
    total = total_completed + total_failed
    error_rate = (total_failed / total) if total else 0.0

    if total == 0:
        health = "idle"
    elif error_rate < 0.1:
        health = "healthy"
    elif error_rate < 0.5:
        health = "degraded"
    else:
        health = "unhealthy"

    return {
        "buckets": buckets,
        "total_completed": total_completed,
        "total_failed": total_failed,
        "error_rate": round(error_rate, 4),
        "health": health,
    }
