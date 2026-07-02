import uuid
from datetime import datetime, timezone

from croniter import croniter
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_queue_role
from app.core.exceptions import NotFoundError, ValidationAppError
from app.database import get_db
from app.models.organization import OrgRole
from app.models.retry_policy import RetryPolicy
from app.models.scheduled_job import ScheduledJob
from app.models.user import User
from app.schemas.job import ScheduledJobCreate, ScheduledJobResponse, ScheduledJobUpdate

router = APIRouter(tags=["scheduled-jobs"])


def _next_run_at(cron_expression: str, tz: str) -> datetime:
    try:
        base = datetime.now(timezone.utc)
        return croniter(cron_expression, base).get_next(datetime)
    except (ValueError, KeyError) as exc:
        raise ValidationAppError(f"Invalid cron expression: {exc}") from exc


@router.post("/api/v1/queues/{queue_id}/scheduled-jobs", response_model=ScheduledJobResponse, status_code=201)
async def create_scheduled_job(
    queue_id: uuid.UUID,
    body: ScheduledJobCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduledJob:
    await require_queue_role(queue_id, OrgRole.ADMIN, db, user)

    retry_policy_id = None
    if body.retry_policy is not None:
        policy = RetryPolicy(**body.retry_policy.model_dump())
        db.add(policy)
        await db.flush()
        retry_policy_id = policy.id

    scheduled_job = ScheduledJob(
        queue_id=queue_id,
        name=body.name,
        payload=body.payload,
        cron_expression=body.cron_expression,
        timezone=body.timezone,
        retry_policy_id=retry_policy_id,
        next_run_at=_next_run_at(body.cron_expression, body.timezone),
        created_by=user.id,
    )
    db.add(scheduled_job)
    await db.commit()
    await db.refresh(scheduled_job)
    return scheduled_job


@router.get("/api/v1/queues/{queue_id}/scheduled-jobs", response_model=list[ScheduledJobResponse])
async def list_scheduled_jobs(
    queue_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[ScheduledJob]:
    await require_queue_role(queue_id, OrgRole.MEMBER, db, user)
    result = await db.scalars(select(ScheduledJob).where(ScheduledJob.queue_id == queue_id))
    return list(result)


async def _get_scheduled_job_or_404(db: AsyncSession, sj_id: uuid.UUID) -> ScheduledJob:
    sj = await db.get(ScheduledJob, sj_id)
    if sj is None:
        raise NotFoundError("Scheduled job not found")
    return sj


@router.patch("/api/v1/scheduled-jobs/{sj_id}", response_model=ScheduledJobResponse)
async def update_scheduled_job(
    sj_id: uuid.UUID,
    body: ScheduledJobUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduledJob:
    sj = await _get_scheduled_job_or_404(db, sj_id)
    await require_queue_role(sj.queue_id, OrgRole.ADMIN, db, user)

    if body.cron_expression is not None:
        sj.cron_expression = body.cron_expression
        sj.next_run_at = _next_run_at(body.cron_expression, sj.timezone)
    if body.is_active is not None:
        sj.is_active = body.is_active

    await db.commit()
    await db.refresh(sj)
    return sj


@router.delete("/api/v1/scheduled-jobs/{sj_id}", status_code=204)
async def delete_scheduled_job(
    sj_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    sj = await _get_scheduled_job_or_404(db, sj_id)
    await require_queue_role(sj.queue_id, OrgRole.ADMIN, db, user)
    await db.delete(sj)
    await db.commit()
