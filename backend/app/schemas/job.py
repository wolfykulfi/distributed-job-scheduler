import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMBase
from app.schemas.queue import RetryPolicyCreate


class JobCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255, description="Worker handler name, e.g. 'http_request'")
    job_type: Literal["immediate", "delayed", "scheduled"] = "immediate"
    payload: dict = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0, le=100)
    idempotency_key: str | None = Field(default=None, max_length=255)
    delay_seconds: int | None = Field(default=None, ge=1, description="Required when job_type='delayed'")
    scheduled_for: datetime | None = Field(default=None, description="Required when job_type='scheduled'")
    retry_policy: RetryPolicyCreate | None = None
    depends_on: list[uuid.UUID] = Field(
        default_factory=list, description="Job IDs (same queue) that must reach 'completed' before this job is claimable"
    )

    @model_validator(mode="after")
    def validate_type_fields(self) -> "JobCreate":
        if self.job_type == "delayed" and self.delay_seconds is None:
            raise ValueError("delay_seconds is required for job_type='delayed'")
        if self.job_type == "scheduled" and self.scheduled_for is None:
            raise ValueError("scheduled_for is required for job_type='scheduled'")
        return self


class BatchItem(BaseModel):
    payload: dict = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=255)


class BatchJobCreate(BaseModel):
    batch_name: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255, description="Worker handler name shared by all items")
    items: list[BatchItem] = Field(min_length=1, max_length=10_000)
    priority: int = Field(default=0, ge=0, le=100)
    retry_policy: RetryPolicyCreate | None = None


class ScheduledJobCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    payload: dict = Field(default_factory=dict)
    cron_expression: str = Field(min_length=1, max_length=100)
    timezone: str = "UTC"
    retry_policy: RetryPolicyCreate | None = None


class ScheduledJobUpdate(BaseModel):
    is_active: bool | None = None
    cron_expression: str | None = None


class ScheduledJobResponse(ORMBase):
    id: uuid.UUID
    queue_id: uuid.UUID
    name: str
    payload: dict
    cron_expression: str
    timezone: str
    is_active: bool
    next_run_at: datetime
    last_run_at: datetime | None


class JobResponse(ORMBase):
    id: uuid.UUID
    queue_id: uuid.UUID
    batch_id: uuid.UUID | None
    scheduled_job_id: uuid.UUID | None
    name: str
    job_type: str
    status: str
    payload: dict
    priority: int
    idempotency_key: str | None
    scheduled_for: datetime | None
    next_retry_at: datetime | None
    attempt_count: int
    claimed_by: uuid.UUID | None
    claimed_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class JobDependencyResponse(BaseModel):
    job_id: uuid.UUID
    name: str
    status: str


class AiSummaryResponse(BaseModel):
    summary: str


class JobExecutionResponse(ORMBase):
    id: uuid.UUID
    attempt_number: int
    status: str
    worker_id: uuid.UUID | None
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    ai_summary: str | None = None
    error_message: str | None
    result: dict | None


class JobLogResponse(ORMBase):
    id: uuid.UUID
    level: str
    message: str
    created_at: datetime


class BatchResponse(ORMBase):
    id: uuid.UUID
    queue_id: uuid.UUID
    name: str
    total_jobs: int


class DeadLetterResponse(ORMBase):
    id: uuid.UUID
    job_id: uuid.UUID
    queue_id: uuid.UUID
    failure_reason: str
    attempt_count: int
    last_error: str | None
    moved_at: datetime
    resolved: bool
