import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase


class WorkerRegisterRequest(BaseModel):
    hostname: str = Field(min_length=1, max_length=255)
    pid: int | None = None
    concurrency: int = Field(default=4, ge=1, le=256)


class WorkerRegisterResponse(BaseModel):
    worker_id: uuid.UUID
    token: str


class WorkerHeartbeatRequest(BaseModel):
    active_job_count: int = Field(ge=0)


class WorkerResponse(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    hostname: str
    pid: int | None
    status: str
    concurrency: int
    started_at: datetime
    last_heartbeat_at: datetime | None
    stopped_at: datetime | None


class PollRequest(BaseModel):
    max_jobs: int = Field(default=1, ge=1, le=100)


class ClaimedJob(BaseModel):
    id: uuid.UUID
    queue_id: uuid.UUID
    name: str
    payload: dict
    attempt_count: int


class JobStartResponse(BaseModel):
    execution_id: uuid.UUID
    attempt_number: int


class JobCompleteRequest(BaseModel):
    result: dict | None = None


class JobFailRequest(BaseModel):
    error_message: str
    error_stacktrace: str | None = None


class JobLogCreate(BaseModel):
    level: str = Field(default="info", pattern="^(debug|info|warn|error)$")
    message: str
