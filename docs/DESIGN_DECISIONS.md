# Design Decisions & Trade-offs

## Stack

**FastAPI + SQLAlchemy 2.0 (async) + asyncpg + PostgreSQL**, chosen for async-native request
handling (workers can poll at high frequency without blocking threads), Pydantic validation
baked into the framework, and Postgres's `SELECT ... FOR UPDATE SKIP LOCKED` being the right
primitive for atomic job claiming without an extra broker (Redis/RabbitMQ) in the loop.

**React + Vite + TypeScript + Tailwind**, polling-based live updates rather than WebSockets.
The assignment explicitly allows either; polling every 3-5s is simpler to reason about, requires
no connection-management code, and is indistinguishable from push for a human staring at a
dashboard. WebSockets are listed as a bonus and were cut given the time budget — see
[Scope cuts](#scope-cuts-given-the-time-budget) below.

## Worker trust boundary: REST + API keys, not direct DB access

The single biggest architectural fork in this project. Two options were considered:

1. **Workers connect directly to Postgres** with shared credentials — simplest, fewest moving
   parts, and still fully safe for atomic claiming (same guarantees either way).
2. **Workers authenticate over REST with a project-scoped API key** (chosen) — a worker calls
   `POST /workers/register` with a project API key, gets back a short-lived JWT scoped to that
   worker, and does everything else (`poll`, `heartbeat`, `start`, `complete`, `fail`, `logs`,
   `drain`, `shutdown`) over HTTP with that token.

Option 2 was chosen because it matches how job schedulers are actually deployed in practice:
worker fleets often run handler code owned by a different team/repo, on different
infrastructure, and shouldn't need live database credentials. It also gives the system a real
"distributed" shape worth demonstrating for this assignment — network-separated components with
an explicit authentication protocol between them, rather than everything sharing one DB
connection string. The cost is more endpoints and a bit more latency per claim; acceptable
for a job scheduler where claim latency of single-digit milliseconds is nowhere near the
bottleneck (job execution time dominates).

## `ScheduledJob` is a separate table from `Job`

Considered making recurring jobs a self-referential `Job` (a "template" row that spawns
"instance" rows pointing back at it via `parent_job_id`). Rejected because the assignment's
requirements explicitly list **Scheduled Jobs** as its own first-class DB entity alongside
`Jobs`, and because a cron definition and a single firing of it have genuinely different
lifecycles and mutable state (`next_run_at`/`last_run_at`/`is_active` belong to the *definition*,
not any one instance). Keeping them separate also means deleting/pausing a recurring definition
can't be confused with cancelling one specific firing.

## Batch jobs = one API call, many `Job` rows, shared `Batch` record

"Batch" is listed alongside immediate/delayed/scheduled/recurring as a *job creation mode*, not
as "one job that internally loops over N items." Interpreted it as: `POST
/queues/{id}/jobs/batch` takes a list of payloads and atomically creates N `Job` rows under one
`Batch` record for aggregate tracking (`total_jobs`, and — with more time — a computed
completed/failed rollup). This composes cleanly with everything else: each item gets its own
retry policy, its own execution history, its own idempotency key, and claims through the exact
same atomic-claim path as any other job.

## Native Postgres enums, not free-text status columns

`job_status`, `job_type`, `worker_status`, `execution_status`, `log_level`, `org_role`,
`retry_strategy` are all native Postgres `ENUM` types (via SQLAlchemy's `Enum`), not
`VARCHAR` + application-level validation. Trade-off: native enums are mildly annoying to alter
later (`ALTER TYPE ... ADD VALUE` has transaction restrictions on older Postgres versions), but
for a schema graded partly on DB design correctness, DB-level integrity beats the flexibility of
free text. **One real bug this caught during development:** SQLAlchemy's `Enum()` defaults to
storing the Python enum member's *name* (`RECURRING_INSTANCE`) rather than its `.value`
(`recurring_instance`) — functionally invisible through the ORM (round-trips fine) but would
have left the raw DB enum labels uppercase and inconsistent with every lowercase snake_case value
in the API/JSON layer. Fixed with a `pg_enum()` helper
([`models/base.py`](../backend/app/models/base.py)) that passes `values_callable` so the stored
label always matches the Python `.value`. Caught by manually inspecting `enum_range()` against a
real Postgres instance, not by unit tests — a good example of why "the ORM tests pass" isn't
sufficient evidence the schema is actually clean.

## Cascade behavior is deliberate per relationship, not blanket `CASCADE`

- `Organization → Project → Queue → Job → JobExecution → JobLog`: cascade delete. Child rows are
  meaningless without their parent (a `Job` with no `Queue` is nonsensical).
- `Worker → Job.claimed_by`, `User → Job.created_by` / `Project.owner_id`: `SET NULL`. A job's
  execution history and audit trail must survive the worker or user that touched it being
  removed — deleting a worker record shouldn't retroactively corrupt job history.
- `RetryPolicy → Queue.default_retry_policy_id` / `Job.retry_policy_id`: `SET NULL`. A retry
  policy can be shared by many queues/jobs; deleting it shouldn't cascade-delete unrelated jobs,
  it should just fall back to the hardcoded default policy (see `job_lifecycle_service.py`).

## Auth model: full org RBAC, not a flat "user owns projects" model

`User —(role)→ OrganizationMember → Organization → Project → Queue → Job`, with three roles
(`owner`/`admin`/`member`) gating write access at the project/queue level
(`core/deps.py::require_project_role`). Chosen over a simpler flat model because the assignment
explicitly asks for "authentication and project management" and lists RBAC as a bonus feature —
building the org layer in from the start was cheaper than retrofitting it later, and it's
directly testable (see `test_member_role_cannot_create_queue`).

**Scope cut:** there is no org-invite endpoint. A registering user becomes the sole `OWNER` of a
brand-new organization; adding other users to that org today requires a direct DB insert (which
is exactly how the RBAC boundary test exercises it). A real product would need
`POST /organizations/{id}/invite`, but it wasn't load-bearing for demonstrating the RBAC
mechanism itself under the time constraint.

## Testing strategy

Integration tests run against a **real Postgres instance**, not SQLite or mocks — deliberately,
because the two properties most worth testing (native enum round-tripping, `FOR UPDATE SKIP
LOCKED` claim semantics under real concurrency) don't exist in SQLite at all. The concurrency
test (`test_claim_concurrency.py`) drives the real HTTP layer with `asyncio.gather` across
multiple registered workers, not a direct unit-test call into `claim_service`, so it's actually
exercising the thing that matters: whether concurrent *requests* can race each other into a
double-claim.

## Scope cuts given the time budget

Explicitly **not implemented**, in order of how much they were considered:
- **Workflow dependencies** (job B waits on job A) — would need a `job_dependencies` join table
  and a "dependencies satisfied" check in the claim query; straightforward extension, cut for time.
- **WebSocket live updates** — polling covers the same user-visible outcome for this use case.
- **Rate limiting, distributed locking (beyond job claiming), queue sharding, event-driven
  execution, AI failure summaries** — all listed bonus items, none load-bearing for the core
  grading criteria (architecture/DB/backend/reliability), cut to protect time spent on getting
  the core lifecycle correct and genuinely tested rather than broad-but-shallow.
- **Org invite flow** — see above.

## What would change for a larger production deployment

- Move `RetryPolicy`/`ScheduledJob` payload validation into a schema-per-handler registry so
  malformed payloads are caught at submission time, not first execution.
- Partition `job_executions`/`job_logs` by time for long-running deployments (they're
  append-mostly and grow unbounded).
- Add a leader-election lock around the scheduler loop instead of relying purely on
  `FOR UPDATE SKIP LOCKED` for cron firing, to avoid redundant work with many scheduler replicas
  (correctness is already guaranteed either way; this would be a throughput optimization).
