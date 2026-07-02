import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_current_worker, require_project_role
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.core.security import create_worker_token, verify_api_key
from app.database import get_db
from app.models.job import Job, JobStatus
from app.models.job_execution import ExecutionStatus, JobExecution
from app.models.job_log import JobLog
from app.models.organization import OrgRole
from app.models.project_api_key import ProjectApiKey
from app.models.user import User
from app.models.worker import Worker, WorkerStatus
from app.models.worker_heartbeat import WorkerHeartbeat
from app.schemas.job import JobLogResponse
from app.schemas.worker import (
    ClaimedJob,
    JobCompleteRequest,
    JobFailRequest,
    JobLogCreate,
    JobStartResponse,
    PollRequest,
    WorkerHeartbeatRequest,
    WorkerRegisterRequest,
    WorkerRegisterResponse,
    WorkerResponse,
)
from app.services.claim_service import claim_jobs_for_worker
from app.services.job_lifecycle_service import complete_job, fail_job, start_job

router = APIRouter(tags=["workers"])


@router.post("/api/v1/workers/register", response_model=WorkerRegisterResponse, status_code=201)
async def register_worker(
    body: WorkerRegisterRequest,
    x_api_key: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> WorkerRegisterResponse:
    if not x_api_key:
        raise AuthenticationError("Missing X-API-Key header")

    prefix = x_api_key[:12]
    candidates = await db.scalars(
        select(ProjectApiKey).where(ProjectApiKey.key_prefix == prefix, ProjectApiKey.revoked_at.is_(None))
    )
    key_row = next((k for k in candidates if verify_api_key(x_api_key, k.key_hash)), None)
    if key_row is None:
        raise AuthenticationError("Invalid API key")

    key_row.last_used_at = datetime.now(timezone.utc)
    worker = Worker(
        project_id=key_row.project_id,
        hostname=body.hostname,
        pid=body.pid,
        concurrency=body.concurrency,
        status=WorkerStatus.ONLINE,
        started_at=datetime.now(timezone.utc),
        last_heartbeat_at=datetime.now(timezone.utc),
    )
    db.add(worker)
    await db.commit()
    await db.refresh(worker)

    token = create_worker_token(worker.id, worker.project_id)
    return WorkerRegisterResponse(worker_id=worker.id, token=token)


@router.post("/api/v1/workers/poll", response_model=list[ClaimedJob])
async def poll(
    body: PollRequest,
    worker: Worker = Depends(get_current_worker),
    db: AsyncSession = Depends(get_db),
) -> list[Job]:
    if worker.status != WorkerStatus.ONLINE:
        return []  # draining/offline workers claim no new work
    return await claim_jobs_for_worker(db, worker, body.max_jobs)


@router.post("/api/v1/workers/heartbeat", status_code=204)
async def heartbeat(
    body: WorkerHeartbeatRequest,
    worker: Worker = Depends(get_current_worker),
    db: AsyncSession = Depends(get_db),
) -> None:
    now = datetime.now(timezone.utc)
    worker.last_heartbeat_at = now
    db.add(WorkerHeartbeat(worker_id=worker.id, heartbeat_at=now, active_job_count=body.active_job_count))
    await db.commit()


@router.post("/api/v1/workers/drain", status_code=204)
async def drain(worker: Worker = Depends(get_current_worker), db: AsyncSession = Depends(get_db)) -> None:
    """Signals the worker is finishing in-flight jobs and will stop claiming new ones."""
    worker.status = WorkerStatus.DRAINING
    await db.commit()


@router.post("/api/v1/workers/shutdown", status_code=204)
async def shutdown(worker: Worker = Depends(get_current_worker), db: AsyncSession = Depends(get_db)) -> None:
    worker.status = WorkerStatus.OFFLINE
    worker.stopped_at = datetime.now(timezone.utc)
    await db.commit()


@router.get("/api/v1/projects/{project_id}/workers", response_model=list[WorkerResponse])
async def list_workers(
    project_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Worker]:
    await require_project_role(project_id, OrgRole.MEMBER, db, user)
    result = await db.scalars(select(Worker).where(Worker.project_id == project_id).order_by(Worker.started_at.desc()))
    return list(result)


async def _get_job_and_execution(db: AsyncSession, job_id: uuid.UUID, worker: Worker) -> tuple[Job, JobExecution]:
    job = await db.get(Job, job_id)
    if job is None or job.claimed_by != worker.id:
        raise NotFoundError("Job not found or not claimed by this worker")
    execution = await db.scalar(
        select(JobExecution)
        .where(JobExecution.job_id == job_id, JobExecution.status == ExecutionStatus.RUNNING)
        .order_by(JobExecution.attempt_number.desc())
    )
    if execution is None:
        raise ConflictError("Job has no in-progress execution; call /start first")
    return job, execution


@router.post("/api/v1/jobs/{job_id}/start", response_model=JobStartResponse)
async def job_start(
    job_id: uuid.UUID, worker: Worker = Depends(get_current_worker), db: AsyncSession = Depends(get_db)
) -> JobStartResponse:
    job = await db.get(Job, job_id)
    if job is None or job.claimed_by != worker.id:
        raise NotFoundError("Job not found or not claimed by this worker")
    if job.status != JobStatus.CLAIMED:
        raise ConflictError(f"Cannot start a job in status '{job.status.value}'")
    execution = await start_job(db, job, worker)
    return JobStartResponse(execution_id=execution.id, attempt_number=execution.attempt_number)


@router.post("/api/v1/jobs/{job_id}/complete", status_code=204)
async def job_complete(
    job_id: uuid.UUID,
    body: JobCompleteRequest,
    worker: Worker = Depends(get_current_worker),
    db: AsyncSession = Depends(get_db),
) -> None:
    job, execution = await _get_job_and_execution(db, job_id, worker)
    await complete_job(db, job, execution, body.result)


@router.post("/api/v1/jobs/{job_id}/fail", status_code=204)
async def job_fail(
    job_id: uuid.UUID,
    body: JobFailRequest,
    worker: Worker = Depends(get_current_worker),
    db: AsyncSession = Depends(get_db),
) -> None:
    job, execution = await _get_job_and_execution(db, job_id, worker)
    await fail_job(db, job, execution, body.error_message, body.error_stacktrace)


@router.post("/api/v1/jobs/{job_id}/logs", response_model=JobLogResponse, status_code=201)
async def job_log(
    job_id: uuid.UUID,
    body: JobLogCreate,
    worker: Worker = Depends(get_current_worker),
    db: AsyncSession = Depends(get_db),
) -> JobLog:
    job, execution = await _get_job_and_execution(db, job_id, worker)
    log = JobLog(job_execution_id=execution.id, level=body.level, message=body.message)
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log
