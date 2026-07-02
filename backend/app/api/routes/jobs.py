import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_queue_role
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.database import get_db
from app.models.job import Batch, Job, JobStatus, JobType
from app.models.job_dependency import JobDependency
from app.models.job_execution import ExecutionStatus, JobExecution
from app.models.job_log import JobLog
from app.models.organization import OrgRole
from app.models.retry_policy import RetryPolicy
from app.models.user import User
from app.schemas.common import Page
from app.schemas.job import (
    AiSummaryResponse,
    BatchJobCreate,
    BatchResponse,
    JobCreate,
    JobDependencyResponse,
    JobExecutionResponse,
    JobLogResponse,
    JobResponse,
)
from app.services.ai_summary_service import summarize_failure
from app.services.notify_service import notify_job_event

router = APIRouter(tags=["jobs"])


async def _resolve_retry_policy_id(db: AsyncSession, retry_policy_create) -> uuid.UUID | None:
    if retry_policy_create is None:
        return None
    policy = RetryPolicy(**retry_policy_create.model_dump())
    db.add(policy)
    await db.flush()
    return policy.id


@router.post("/api/v1/queues/{queue_id}/jobs", response_model=JobResponse, status_code=201)
async def create_job(
    queue_id: uuid.UUID,
    body: JobCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Job:
    await require_queue_role(queue_id, OrgRole.MEMBER, db, user)

    if body.idempotency_key:
        existing = await db.scalar(
            select(Job).where(Job.queue_id == queue_id, Job.idempotency_key == body.idempotency_key)
        )
        if existing is not None:
            raise ConflictError(f"An active job with idempotency_key='{body.idempotency_key}' already exists")

    retry_policy_id = await _resolve_retry_policy_id(db, body.retry_policy)

    if body.job_type == "immediate":
        job_type, status, scheduled_for = JobType.IMMEDIATE, JobStatus.QUEUED, None
    elif body.job_type == "delayed":
        job_type = JobType.DELAYED
        status = JobStatus.SCHEDULED
        scheduled_for = datetime.now(timezone.utc) + timedelta(seconds=body.delay_seconds)
    else:  # scheduled
        job_type, status, scheduled_for = JobType.SCHEDULED, JobStatus.SCHEDULED, body.scheduled_for

    if body.depends_on:
        found = set(
            await db.scalars(select(Job.id).where(Job.queue_id == queue_id, Job.id.in_(body.depends_on)))
        )
        missing = set(body.depends_on) - found
        if missing:
            raise ValidationAppError(
                f"depends_on job(s) not found in this queue: {', '.join(str(m) for m in missing)}"
            )

    job = Job(
        queue_id=queue_id,
        name=body.name,
        job_type=job_type,
        status=status,
        payload=body.payload,
        priority=body.priority,
        idempotency_key=body.idempotency_key,
        scheduled_for=scheduled_for,
        retry_policy_id=retry_policy_id,
        created_by=user.id,
    )
    db.add(job)
    await db.flush()  # assign job.id before inserting dependency edges

    for dep_id in body.depends_on:
        db.add(JobDependency(job_id=job.id, depends_on_job_id=dep_id))

    await notify_job_event(db, queue_id, job.id, job.status.value)
    await db.commit()
    await db.refresh(job)
    return job


@router.post("/api/v1/queues/{queue_id}/jobs/batch", response_model=BatchResponse, status_code=201)
async def create_batch(
    queue_id: uuid.UUID,
    body: BatchJobCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Batch:
    await require_queue_role(queue_id, OrgRole.MEMBER, db, user)
    retry_policy_id = await _resolve_retry_policy_id(db, body.retry_policy)

    batch = Batch(queue_id=queue_id, name=body.batch_name, total_jobs=len(body.items), created_by=user.id)
    db.add(batch)
    await db.flush()

    for item in body.items:
        db.add(
            Job(
                queue_id=queue_id,
                batch_id=batch.id,
                name=body.name,
                job_type=JobType.BATCH,
                status=JobStatus.QUEUED,
                payload=item.payload,
                priority=body.priority,
                idempotency_key=item.idempotency_key,
                retry_policy_id=retry_policy_id,
                created_by=user.id,
            )
        )
    await db.commit()
    await db.refresh(batch)
    return batch


@router.get("/api/v1/queues/{queue_id}/jobs", response_model=Page[JobResponse])
async def list_jobs(
    queue_id: uuid.UUID,
    status: JobStatus | None = None,
    job_type: JobType | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Page:
    await require_queue_role(queue_id, OrgRole.MEMBER, db, user)

    stmt = select(Job).where(Job.queue_id == queue_id)
    count_stmt = select(func.count()).select_from(Job).where(Job.queue_id == queue_id)
    if status is not None:
        stmt = stmt.where(Job.status == status)
        count_stmt = count_stmt.where(Job.status == status)
    if job_type is not None:
        stmt = stmt.where(Job.job_type == job_type)
        count_stmt = count_stmt.where(Job.job_type == job_type)

    total = await db.scalar(count_stmt)
    rows = await db.scalars(stmt.order_by(Job.created_at.desc()).limit(limit).offset(offset))
    return Page(items=list(rows), total=total or 0, limit=limit, offset=offset)


async def _get_job_or_404(db: AsyncSession, job_id: uuid.UUID) -> Job:
    job = await db.get(Job, job_id)
    if job is None:
        raise NotFoundError("Job not found")
    return job


@router.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> Job:
    job = await _get_job_or_404(db, job_id)
    await require_queue_role(job.queue_id, OrgRole.MEMBER, db, user)
    return job


@router.get("/api/v1/jobs/{job_id}/dependencies", response_model=list[JobDependencyResponse])
async def get_job_dependencies(
    job_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[JobDependencyResponse]:
    job = await _get_job_or_404(db, job_id)
    await require_queue_role(job.queue_id, OrgRole.MEMBER, db, user)
    rows = await db.execute(
        select(Job.id, Job.name, Job.status)
        .join(JobDependency, JobDependency.depends_on_job_id == Job.id)
        .where(JobDependency.job_id == job_id)
    )
    return [JobDependencyResponse(job_id=r.id, name=r.name, status=r.status.value) for r in rows]


@router.get("/api/v1/jobs/{job_id}/executions", response_model=list[JobExecutionResponse])
async def get_job_executions(
    job_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[JobExecution]:
    job = await _get_job_or_404(db, job_id)
    await require_queue_role(job.queue_id, OrgRole.MEMBER, db, user)
    result = await db.scalars(
        select(JobExecution).where(JobExecution.job_id == job_id).order_by(JobExecution.attempt_number)
    )
    return list(result)


@router.post("/api/v1/jobs/{job_id}/executions/{execution_id}/ai-summary", response_model=AiSummaryResponse)
async def get_ai_failure_summary(
    job_id: uuid.UUID,
    execution_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiSummaryResponse:
    job = await _get_job_or_404(db, job_id)
    await require_queue_role(job.queue_id, OrgRole.MEMBER, db, user)

    execution = await db.get(JobExecution, execution_id)
    if execution is None or execution.job_id != job_id:
        raise NotFoundError("Execution not found")
    if execution.status != ExecutionStatus.FAILED:
        raise ConflictError("AI summaries are only available for failed executions")

    if execution.ai_summary is None:
        execution.ai_summary = await summarize_failure(
            job.name, execution.error_message or "(no error message)", execution.error_stacktrace
        )
        await db.commit()

    return AiSummaryResponse(summary=execution.ai_summary)


@router.get("/api/v1/jobs/{job_id}/logs", response_model=list[JobLogResponse])
async def get_job_logs(
    job_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[JobLog]:
    job = await _get_job_or_404(db, job_id)
    await require_queue_role(job.queue_id, OrgRole.MEMBER, db, user)
    result = await db.scalars(
        select(JobLog)
        .join(JobExecution, JobLog.job_execution_id == JobExecution.id)
        .where(JobExecution.job_id == job_id)
        .order_by(JobLog.created_at)
    )
    return list(result)


@router.post("/api/v1/jobs/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Job:
    job = await _get_job_or_404(db, job_id)
    await require_queue_role(job.queue_id, OrgRole.ADMIN, db, user)
    if job.status not in (JobStatus.QUEUED, JobStatus.SCHEDULED):
        raise ConflictError(f"Cannot cancel a job in status '{job.status.value}'")
    job.status = JobStatus.CANCELLED
    await notify_job_event(db, job.queue_id, job.id, JobStatus.CANCELLED.value)
    await db.commit()
    await db.refresh(job)
    return job
