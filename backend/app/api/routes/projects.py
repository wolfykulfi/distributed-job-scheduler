import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_project_role
from app.core.exceptions import NotFoundError
from app.core.security import generate_api_key, hash_api_key
from app.database import get_db
from app.models.organization import OrgRole
from app.models.project import Project
from app.models.project_api_key import ProjectApiKey
from app.models.user import User
from app.schemas.project import ApiKeyCreate, ApiKeyCreateResponse, ApiKeyResponse, ProjectResponse

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Project:
    return await require_project_role(project_id, OrgRole.MEMBER, db, user)


@router.post("/{project_id}/api-keys", response_model=ApiKeyCreateResponse, status_code=201)
async def create_api_key(
    project_id: uuid.UUID,
    body: ApiKeyCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreateResponse:
    """Issues a key workers use to register with this project. Raw key is returned once only."""
    await require_project_role(project_id, OrgRole.ADMIN, db, user)

    raw_key, prefix = generate_api_key()
    key = ProjectApiKey(
        project_id=project_id, name=body.name, key_prefix=prefix, key_hash=hash_api_key(raw_key), created_by=user.id
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return ApiKeyCreateResponse(id=key.id, name=key.name, api_key=raw_key)


@router.get("/{project_id}/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    project_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[ProjectApiKey]:
    await require_project_role(project_id, OrgRole.ADMIN, db, user)
    result = await db.scalars(select(ProjectApiKey).where(ProjectApiKey.project_id == project_id))
    return list(result)


@router.delete("/{project_id}/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await require_project_role(project_id, OrgRole.ADMIN, db, user)
    key = await db.get(ProjectApiKey, key_id)
    if key is None or key.project_id != project_id:
        raise NotFoundError("API key not found")
    key.revoked_at = datetime.now(timezone.utc)
    await db.commit()
