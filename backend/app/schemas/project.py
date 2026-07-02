import uuid

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ProjectResponse(ORMBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    owner_id: uuid.UUID | None


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ApiKeyCreateResponse(BaseModel):
    id: uuid.UUID
    name: str
    api_key: str  # raw key, shown once


class ApiKeyResponse(ORMBase):
    id: uuid.UUID
    name: str
    key_prefix: str
    revoked_at: str | None = None
    last_used_at: str | None = None
