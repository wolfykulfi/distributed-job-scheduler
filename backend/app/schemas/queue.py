import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase


class RetryPolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    strategy: str = Field(default="exponential", pattern="^(fixed|linear|exponential)$")
    max_attempts: int = Field(default=5, ge=1, le=50)
    base_delay_seconds: int = Field(default=10, ge=1)
    max_delay_seconds: int = Field(default=3600, ge=1)
    multiplier: float = Field(default=2.0, ge=1.0, le=10.0)


class RetryPolicyResponse(ORMBase):
    id: uuid.UUID
    name: str
    strategy: str
    max_attempts: int
    base_delay_seconds: int
    max_delay_seconds: int
    multiplier: float


class QueueCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    priority: int = Field(default=0, ge=0, le=100)
    max_concurrency: int = Field(default=4, ge=1, le=1000)
    retry_policy: RetryPolicyCreate | None = None


class QueueUpdate(BaseModel):
    description: str | None = None
    priority: int | None = Field(default=None, ge=0, le=100)
    max_concurrency: int | None = Field(default=None, ge=1, le=1000)


class QueueResponse(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    priority: int
    max_concurrency: int
    is_paused: bool
    default_retry_policy_id: uuid.UUID | None


class QueueStats(BaseModel):
    queued: int
    scheduled: int
    claimed: int
    running: int
    completed: int
    failed: int
    dead_letter: int
    cancelled: int


class ThroughputBucket(BaseModel):
    bucket_start: datetime
    completed: int
    failed: int


class ThroughputResponse(BaseModel):
    buckets: list[ThroughputBucket]
    total_completed: int
    total_failed: int
    error_rate: float
    health: str
