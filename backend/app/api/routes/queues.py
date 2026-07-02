import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_project_role, require_queue_role
from app.database import get_db
from app.models.job import Job, JobStatus
from app.models.organization import OrgRole
from app.models.queue import Queue
from app.models.retry_policy import RetryPolicy
from app.models.user import User
from app.schemas.queue import QueueCreate, QueueResponse, QueueStats, QueueUpdate

router = APIRouter(tags=["queues"])


@router.post("/api/v1/projects/{project_id}/queues", response_model=QueueResponse, status_code=201)
async def create_queue(
    project_id: uuid.UUID,
    body: QueueCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Queue:
    await require_project_role(project_id, OrgRole.ADMIN, db, user)

    retry_policy_id = None
    if body.retry_policy is not None:
        policy = RetryPolicy(**body.retry_policy.model_dump())
        db.add(policy)
        await db.flush()
        retry_policy_id = policy.id

    queue = Queue(
        project_id=project_id,
        name=body.name,
        description=body.description,
        priority=body.priority,
        max_concurrency=body.max_concurrency,
        default_retry_policy_id=retry_policy_id,
    )
    db.add(queue)
    await db.commit()
    await db.refresh(queue)
    return queue


@router.get("/api/v1/projects/{project_id}/queues", response_model=list[QueueResponse])
async def list_queues(
    project_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Queue]:
    await require_project_role(project_id, OrgRole.MEMBER, db, user)
    result = await db.scalars(select(Queue).where(Queue.project_id == project_id))
    return list(result)


@router.get("/api/v1/queues/{queue_id}", response_model=QueueResponse)
async def get_queue(
    queue_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Queue:
    return await require_queue_role(queue_id, OrgRole.MEMBER, db, user)


@router.patch("/api/v1/queues/{queue_id}", response_model=QueueResponse)
async def update_queue(
    queue_id: uuid.UUID,
    body: QueueUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Queue:
    queue = await require_queue_role(queue_id, OrgRole.ADMIN, db, user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(queue, field, value)
    await db.commit()
    await db.refresh(queue)
    return queue


@router.post("/api/v1/queues/{queue_id}/pause", response_model=QueueResponse)
async def pause_queue(
    queue_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Queue:
    queue = await require_queue_role(queue_id, OrgRole.ADMIN, db, user)
    queue.is_paused = True
    await db.commit()
    await db.refresh(queue)
    return queue


@router.post("/api/v1/queues/{queue_id}/resume", response_model=QueueResponse)
async def resume_queue(
    queue_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Queue:
    queue = await require_queue_role(queue_id, OrgRole.ADMIN, db, user)
    queue.is_paused = False
    await db.commit()
    await db.refresh(queue)
    return queue


@router.get("/api/v1/queues/{queue_id}/stats", response_model=QueueStats)
async def queue_stats(
    queue_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> QueueStats:
    await require_queue_role(queue_id, OrgRole.MEMBER, db, user)
    rows = await db.execute(
        select(Job.status, func.count()).where(Job.queue_id == queue_id).group_by(Job.status)
    )
    counts = {status.value: 0 for status in JobStatus}
    for status, count in rows.all():
        counts[status.value] = count
    return QueueStats(**counts)
