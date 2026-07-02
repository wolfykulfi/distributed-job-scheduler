# Entity-Relationship Diagram

```mermaid
erDiagram
    USER ||--o{ ORGANIZATION_MEMBER : "has"
    ORGANIZATION ||--o{ ORGANIZATION_MEMBER : "has"
    ORGANIZATION ||--o{ PROJECT : "owns"
    PROJECT ||--o{ QUEUE : "owns"
    PROJECT ||--o{ PROJECT_API_KEY : "issues"
    PROJECT ||--o{ WORKER : "hosts"
    QUEUE ||--o{ JOB : "contains"
    QUEUE ||--o{ SCHEDULED_JOB : "contains"
    QUEUE ||--o{ BATCH : "contains"
    QUEUE }o--o| RETRY_POLICY : "default policy"
    JOB }o--o| RETRY_POLICY : "override policy"
    JOB }o--o| BATCH : "belongs to"
    JOB }o--o| SCHEDULED_JOB : "spawned by"
    JOB }o--o| WORKER : "claimed by"
    JOB ||--o{ JOB_EXECUTION : "attempts"
    JOB ||--o| DEAD_LETTER_JOB : "moved to"
    JOB_EXECUTION ||--o{ JOB_LOG : "logs"
    JOB_EXECUTION }o--o| WORKER : "executed by"
    WORKER ||--o{ WORKER_HEARTBEAT : "pings"

    USER {
        uuid id PK
        string email UK
        string hashed_password
        string full_name
        bool is_active
    }
    ORGANIZATION {
        uuid id PK
        string name
    }
    ORGANIZATION_MEMBER {
        uuid id PK
        uuid organization_id FK
        uuid user_id FK
        enum role "owner/admin/member"
    }
    PROJECT {
        uuid id PK
        uuid organization_id FK
        string name
        string description
        uuid owner_id FK
    }
    PROJECT_API_KEY {
        uuid id PK
        uuid project_id FK
        string name
        string key_prefix
        string key_hash
        timestamp revoked_at
        timestamp last_used_at
    }
    RETRY_POLICY {
        uuid id PK
        string name
        enum strategy "fixed/linear/exponential"
        int max_attempts
        int base_delay_seconds
        int max_delay_seconds
        float multiplier
    }
    QUEUE {
        uuid id PK
        uuid project_id FK
        string name
        int priority
        int max_concurrency
        bool is_paused
        uuid default_retry_policy_id FK
    }
    BATCH {
        uuid id PK
        uuid queue_id FK
        string name
        int total_jobs
    }
    SCHEDULED_JOB {
        uuid id PK
        uuid queue_id FK
        uuid retry_policy_id FK
        string name
        jsonb payload
        string cron_expression
        string timezone
        bool is_active
        timestamp next_run_at
        timestamp last_run_at
    }
    JOB {
        uuid id PK
        uuid queue_id FK
        uuid batch_id FK
        uuid scheduled_job_id FK
        uuid retry_policy_id FK
        uuid claimed_by FK
        string name
        enum job_type "immediate/delayed/scheduled/recurring_instance/batch"
        enum status "queued/scheduled/claimed/running/completed/failed/dead_letter/cancelled"
        jsonb payload
        int priority
        string idempotency_key
        timestamp scheduled_for
        timestamp next_retry_at
        int attempt_count
        timestamp claimed_at
        timestamp started_at
        timestamp completed_at
    }
    JOB_EXECUTION {
        uuid id PK
        uuid job_id FK
        uuid worker_id FK
        int attempt_number
        enum status "running/succeeded/failed"
        timestamp started_at
        timestamp finished_at
        int duration_ms
        text error_message
        text error_stacktrace
        jsonb result
    }
    JOB_LOG {
        uuid id PK
        uuid job_execution_id FK
        enum level "debug/info/warn/error"
        text message
    }
    WORKER {
        uuid id PK
        uuid project_id FK
        string hostname
        int pid
        enum status "online/draining/offline"
        int concurrency
        timestamp started_at
        timestamp last_heartbeat_at
        timestamp stopped_at
    }
    WORKER_HEARTBEAT {
        uuid id PK
        uuid worker_id FK
        timestamp heartbeat_at
        int active_job_count
    }
    DEAD_LETTER_JOB {
        uuid id PK
        uuid job_id FK "unique"
        uuid queue_id FK
        jsonb payload
        text failure_reason
        int attempt_count
        text last_error
        timestamp moved_at
        bool resolved
        uuid resolved_by FK
    }
```

## Key design choices

**Primary keys.** Every table uses a UUIDv4 surrogate key rather than an auto-increment
integer. Jobs are created concurrently by many API callers and workers across (potentially)
multiple app server instances; UUIDs need no central sequence coordination and don't leak
row-count/creation-order information the way serial IDs do.

**Foreign keys & cascade behavior** (see [`DESIGN_DECISIONS.md`](DESIGN_DECISIONS.md) for the
full reasoning): deleting an `Organization` → `Project` → `Queue` cascades down, since child
rows are meaningless without the parent. Deleting a `Worker` or `User` only nulls out
references (`Job.claimed_by`, `Job.created_by`) — a job's audit trail must survive its worker
or creator being removed.

**Indexes.**
- `ix_job_claim_lookup (queue_id, status, priority)` — covers the atomic claim query so it
  stays an index scan under load, not a sequential scan.
- `uq_job_idempotency_active (queue_id, idempotency_key) WHERE idempotency_key IS NOT NULL` —
  partial unique index; only jobs that opt into an idempotency key are deduplicated, and
  completed/retried jobs don't permanently block reuse of a key.
- `ix_scheduled_jobs (is_active, next_run_at)` — the scheduler loop's hot query.

**Normalization.** `JobExecution` is a separate table from `Job`, not a JSON blob on `Job`,
so full retry history survives independent of the job's current state, and so per-attempt
metrics (duration, error) can be queried/aggregated directly. `RetryPolicy` is its own table
(not columns inlined on `Queue`/`Job`) so a policy can be defined once and reused, and so a
`Job` can override its queue's default policy without duplicating the strategy fields.
