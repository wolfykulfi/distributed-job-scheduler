from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dead_letter import DeadLetterJob
from app.models.job import Job, JobStatus
from app.models.job_execution import ExecutionStatus, JobExecution
from app.models.queue import Queue
from app.models.retry_policy import RetryPolicy, RetryStrategy
from app.models.worker import Worker
from app.services.notify_service import notify_job_event
from app.services.retry_service import compute_backoff_seconds

# Applied when neither the job nor its queue defines a retry policy.
_DEFAULT_POLICY = RetryPolicy(
    name="__default__", strategy=RetryStrategy.EXPONENTIAL, max_attempts=3,
    base_delay_seconds=10, max_delay_seconds=300, multiplier=2.0,
)


async def _effective_retry_policy(db: AsyncSession, job: Job) -> RetryPolicy:
    if job.retry_policy_id is not None:
        policy = await db.get(RetryPolicy, job.retry_policy_id)
        if policy is not None:
            return policy
    queue = await db.get(Queue, job.queue_id)
    if queue and queue.default_retry_policy_id is not None:
        policy = await db.get(RetryPolicy, queue.default_retry_policy_id)
        if policy is not None:
            return policy
    return _DEFAULT_POLICY


async def start_job(db: AsyncSession, job: Job, worker: Worker) -> JobExecution:
    now = datetime.now(timezone.utc)
    job.status = JobStatus.RUNNING
    job.started_at = now
    job.attempt_count += 1

    execution = JobExecution(
        job_id=job.id, worker_id=worker.id, attempt_number=job.attempt_count,
        status=ExecutionStatus.RUNNING, started_at=now,
    )
    db.add(execution)
    await notify_job_event(db, job.queue_id, job.id, JobStatus.RUNNING.value)
    await db.commit()
    await db.refresh(execution)
    return execution


async def complete_job(db: AsyncSession, job: Job, execution: JobExecution, result: dict | None) -> None:
    now = datetime.now(timezone.utc)
    job.status = JobStatus.COMPLETED
    job.completed_at = now

    execution.status = ExecutionStatus.SUCCEEDED
    execution.finished_at = now
    execution.duration_ms = int((now - execution.started_at).total_seconds() * 1000)
    execution.result = result
    await notify_job_event(db, job.queue_id, job.id, JobStatus.COMPLETED.value)
    await db.commit()


async def fail_job(
    db: AsyncSession, job: Job, execution: JobExecution, error_message: str, error_stacktrace: str | None
) -> None:
    now = datetime.now(timezone.utc)
    execution.status = ExecutionStatus.FAILED
    execution.finished_at = now
    execution.duration_ms = int((now - execution.started_at).total_seconds() * 1000)
    execution.error_message = error_message
    execution.error_stacktrace = error_stacktrace

    policy = await _effective_retry_policy(db, job)

    if job.attempt_count < policy.max_attempts:
        delay = compute_backoff_seconds(
            policy.strategy, job.attempt_count, policy.base_delay_seconds,
            policy.max_delay_seconds, policy.multiplier,
        )
        job.status = JobStatus.SCHEDULED
        job.next_retry_at = now + timedelta(seconds=delay)
        job.scheduled_for = job.next_retry_at
    else:
        job.status = JobStatus.DEAD_LETTER
        db.add(
            DeadLetterJob(
                job_id=job.id, queue_id=job.queue_id, payload=job.payload,
                failure_reason=f"Exceeded max_attempts={policy.max_attempts}",
                attempt_count=job.attempt_count, last_error=error_message, moved_at=now,
            )
        )

    await notify_job_event(db, job.queue_id, job.id, job.status.value)
    await db.commit()
