# API Documentation

Full interactive OpenAPI/Swagger docs are served automatically at `GET /docs` (and machine-
readable spec at `GET /openapi.json`) whenever the API server is running. This document is a
narrative companion, organized by resource and by *who* calls each endpoint.

All authenticated endpoints take a `Bearer` token. There are two distinct token types that are
**not interchangeable**:
- **User JWT** — from `/auth/login` or `/auth/register`. Used by the dashboard / any human-facing client.
- **Worker JWT** — from `/workers/register`, itself gated by a project `X-API-Key`. Used only by worker processes.

Errors follow a consistent shape: `{"error": {"code": "...", "message": "...", "details"?: [...]}}`
with the HTTP status matching the error (`404` not_found, `409` conflict, `401` unauthenticated,
`403` permission_denied, `422` validation_error).

## Auth (`/api/v1/auth`)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/register` | none | Creates a user **and** a brand-new organization (caller becomes `OWNER`). Returns a user JWT. |
| POST | `/login` | none | Returns a user JWT. |
| GET | `/me` | user | Current user profile. |

## Organizations & Projects

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/organizations` | user | Organizations the caller belongs to. |
| POST | `/api/v1/organizations/{org_id}/projects` | user, `ADMIN`+ | Create a project. |
| GET | `/api/v1/organizations/{org_id}/projects` | user, `MEMBER`+ | List projects in an org. |
| GET | `/api/v1/projects/{project_id}` | user, `MEMBER`+ | Project detail. |
| POST | `/api/v1/projects/{project_id}/api-keys` | user, `ADMIN`+ | Issue a worker API key. **Raw key returned once, only in this response.** |
| GET | `/api/v1/projects/{project_id}/api-keys` | user, `ADMIN`+ | List keys (hashes only). |
| DELETE | `/api/v1/projects/{project_id}/api-keys/{key_id}` | user, `ADMIN`+ | Revoke a key. |

## Queues

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/projects/{project_id}/queues` | user, `ADMIN`+ | Create a queue; optionally embeds a `retry_policy` to set as the queue's default. |
| GET | `/api/v1/projects/{project_id}/queues` | user, `MEMBER`+ | List queues in a project. |
| GET | `/api/v1/queues/{queue_id}` | user, `MEMBER`+ | Queue detail. |
| PATCH | `/api/v1/queues/{queue_id}` | user, `ADMIN`+ | Update description/priority/max_concurrency. |
| POST | `/api/v1/queues/{queue_id}/pause` \| `/resume` | user, `ADMIN`+ | Stop/resume workers claiming from this queue. |
| GET | `/api/v1/queues/{queue_id}/stats` | user, `MEMBER`+ | Job counts grouped by status. |
| GET | `/api/v1/queues/{queue_id}/throughput` | user, `MEMBER`+ | Time-bucketed completed/failed counts over a sliding window (`window_minutes`, default 60; `bucket_minutes`, default 5) plus an overall `error_rate` and a derived `health` (`idle` \| `healthy` \| `degraded` \| `unhealthy`). Powers the dashboard's throughput/health chart. |

## Jobs

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/queues/{queue_id}/jobs` | user, `MEMBER`+ | Create an `immediate` \| `delayed` \| `scheduled` job. `delay_seconds` required for `delayed`, `scheduled_for` required for `scheduled`. Optional `idempotency_key` (409 on duplicate active key), per-job `retry_policy` override, and `depends_on: [job_id, ...]` — job IDs in the same queue that must reach `completed` before this one is claimable (422 if any ID doesn't exist in the queue). |
| POST | `/api/v1/queues/{queue_id}/jobs/batch` | user, `MEMBER`+ | Bulk-create N jobs sharing one handler `name` and retry policy, grouped under a `Batch`. |
| GET | `/api/v1/queues/{queue_id}/jobs` | user, `MEMBER`+ | Paginated (`limit`/`offset`), filterable by `status` and `job_type`. |
| GET | `/api/v1/jobs/{job_id}` | user, `MEMBER`+ | Job detail. |
| GET | `/api/v1/jobs/{job_id}/dependencies` | user, `MEMBER`+ | This job's `depends_on` edges, each with the dependency's live `name`/`status`. |
| GET | `/api/v1/jobs/{job_id}/executions` | user, `MEMBER`+ | Full attempt history. |
| POST | `/api/v1/jobs/{job_id}/executions/{execution_id}/ai-summary` | user, `MEMBER`+ | Only valid for a `failed` execution. Returns `{summary}` — a Groq-generated plain-English diagnosis, cached on first call. `503 ai_summary_unavailable` if no `GROQ_API_KEY` is configured or the Groq call fails. |
| GET | `/api/v1/jobs/{job_id}/logs` | user, `MEMBER`+ | Log lines across all attempts. |
| POST | `/api/v1/jobs/{job_id}/cancel` | user, `ADMIN`+ | Only valid from `queued`/`scheduled`. |

## Recurring jobs (`/scheduled-jobs`)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/queues/{queue_id}/scheduled-jobs` | user, `ADMIN`+ | Create a cron definition; `next_run_at` computed immediately via `croniter`. |
| GET | `/api/v1/queues/{queue_id}/scheduled-jobs` | user, `MEMBER`+ | List definitions for a queue. |
| PATCH | `/api/v1/scheduled-jobs/{sj_id}` | user, `ADMIN`+ | Update `cron_expression` (recomputes `next_run_at`) and/or `is_active` (pause/resume firing). |
| DELETE | `/api/v1/scheduled-jobs/{sj_id}` | user, `ADMIN`+ | Remove the definition (does not delete already-spawned `Job` rows). |

## Dead letter queue

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/queues/{queue_id}/dead-letter` | user, `MEMBER`+ | Unresolved DLQ entries (`?resolved=true` for resolved ones). |
| POST | `/api/v1/dead-letter/{dlq_id}/retry` | user, `ADMIN`+ | Resets the original job to `queued` with `attempt_count = 0` and marks the DLQ entry resolved. |

## Workers (worker-facing, JWT from `/workers/register`)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/workers/register` | `X-API-Key` header | Registers a `Worker` row, returns `{worker_id, token}`. |
| POST | `/api/v1/workers/poll` | worker | Atomically claims up to `max_jobs` across the project's unpaused queues (priority order, respecting each queue's `max_concurrency`). |
| POST | `/api/v1/workers/heartbeat` | worker | Reports `active_job_count`; updates `last_heartbeat_at` and appends a `WorkerHeartbeat` row. |
| POST | `/api/v1/workers/drain` | worker | Marks the worker `draining` — server-side signal that it will claim no more work. |
| POST | `/api/v1/workers/shutdown` | worker | Marks the worker `offline`. |
| POST | `/api/v1/jobs/{job_id}/start` | worker | `claimed → running`; creates the `JobExecution` row for this attempt. |
| POST | `/api/v1/jobs/{job_id}/complete` | worker | `running → completed`. |
| POST | `/api/v1/jobs/{job_id}/fail` | worker | `running →` `scheduled` (retry, backoff applied) or `dead_letter` (attempts exhausted). |
| POST | `/api/v1/jobs/{job_id}/logs` | worker | Appends a `JobLog` line to the current execution. Called automatically by `run_worker.py` at claim, completion, and failure (best-effort — a logging failure never fails the job), so every execution has a visible log trail without handlers needing to log anything themselves. |

## Workers (user-facing)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/projects/{project_id}/workers` | user, `MEMBER`+ | List workers registered to a project, with live status/heartbeat. |

## Live updates (WebSocket)

| Path | Auth | Description |
|---|---|---|
| `WS /api/v1/ws/queues/{queue_id}` | user JWT as `?token=` query param (not a header — browsers can't set one on the WebSocket handshake) | Pushes `{queue_id, job_id, status}` for every state change on jobs in this queue, sourced from Postgres `LISTEN`/`NOTIFY`. Purely a latency optimization: the dashboard's polling already keeps it correct if this never connects or drops. See [`ARCHITECTURE.md`](ARCHITECTURE.md#websocket-live-updates) for the full flow. |
