import uuid

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_token
from app.database import get_db
from app.models.organization import OrgRole, OrganizationMember
from app.models.project import Project
from app.models.user import User
from app.models.worker import Worker

_ROLE_RANK = {OrgRole.MEMBER: 0, OrgRole.ADMIN: 1, OrgRole.OWNER: 2}


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthenticationError("Missing or malformed Authorization header")
    return authorization.split(" ", 1)[1]


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = _extract_bearer_token(authorization)
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise AuthenticationError(str(exc)) from exc
    if payload.get("type") != "user":
        raise AuthenticationError("Token is not a user token")
    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive")
    return user


async def get_current_worker(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Worker:
    token = _extract_bearer_token(authorization)
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise AuthenticationError(str(exc)) from exc
    if payload.get("type") != "worker":
        raise AuthenticationError("Token is not a worker token")
    worker = await db.get(Worker, uuid.UUID(payload["sub"]))
    if worker is None:
        raise AuthenticationError("Worker not found")
    return worker


async def require_project_role(
    project_id: uuid.UUID,
    min_role: OrgRole,
    db: AsyncSession,
    user: User,
) -> Project:
    """Loads the project and asserts `user` has at least `min_role` in its organization.

    Kept as a plain async function (not a FastAPI Depends) because the project_id comes from
    the route's path parameter, which Depends can't easily thread through without extra
    boilerplate for every single route -- callers invoke this at the top of each handler.
    """
    project = await db.get(Project, project_id)
    if project is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Project not found")

    membership = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == project.organization_id,
            OrganizationMember.user_id == user.id,
        )
    )
    if membership is None or _ROLE_RANK[membership.role] < _ROLE_RANK[min_role]:
        raise PermissionDeniedError("Insufficient role for this project")
    return project


async def require_queue_role(
    queue_id: uuid.UUID,
    min_role: OrgRole,
    db: AsyncSession,
    user: User,
):
    """Loads the queue and asserts `user` has at least `min_role` in its project's organization."""
    from app.core.exceptions import NotFoundError
    from app.models.queue import Queue

    queue = await db.get(Queue, queue_id)
    if queue is None:
        raise NotFoundError("Queue not found")
    await require_project_role(queue.project_id, min_role, db, user)
    return queue
