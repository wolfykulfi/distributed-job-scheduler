import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.exceptions import PermissionDeniedError
from app.database import get_db
from app.models.organization import OrgRole, Organization, OrganizationMember
from app.models.project import Project
from app.models.user import User
from app.schemas.organization import OrganizationResponse
from app.schemas.project import ProjectCreate, ProjectResponse

router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])


@router.get("", response_model=list[OrganizationResponse])
async def list_my_organizations(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Organization]:
    result = await db.scalars(
        select(Organization)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id)
    )
    return list(result)


@router.post("/{org_id}/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    org_id: uuid.UUID,
    body: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    membership = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id, OrganizationMember.user_id == user.id
        )
    )
    if membership is None or membership.role == OrgRole.MEMBER:
        raise PermissionDeniedError("Only org admins/owners can create projects")

    project = Project(organization_id=org_id, name=body.name, description=body.description, owner_id=user.id)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/{org_id}/projects", response_model=list[ProjectResponse])
async def list_projects(
    org_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Project]:
    membership = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id, OrganizationMember.user_id == user.id
        )
    )
    if membership is None:
        raise PermissionDeniedError("Not a member of this organization")

    result = await db.scalars(select(Project).where(Project.organization_id == org_id))
    return list(result)
