# Distributed Job Scheduler

A production-inspired distributed job scheduling platform: queues, five job-creation modes
(immediate/delayed/scheduled/recurring/batch), a worker fleet that claims jobs atomically and
executes them concurrently, retries with configurable backoff, a dead letter queue, and a
dashboard to watch it all happen.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the system design,
[`docs/ER_DIAGRAM.md`](docs/ER_DIAGRAM.md) for the schema,
[`docs/API.md`](docs/API.md) for endpoint reference, and
[`docs/DESIGN_DECISIONS.md`](docs/DESIGN_DECISIONS.md) for the trade-offs behind all of it.

## Stack

Backend: FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL + Alembic.
Frontend: React + TypeScript + Vite + Tailwind CSS.

## Quick start (Docker)

```bash
docker compose up postgres api frontend
```

- API: http://localhost:8000 (interactive docs at `/docs`)
- Dashboard: http://localhost:5173

Then, to actually run jobs, you need at least one worker:

1. Open the dashboard, register, create a project and a queue.
2. On the project page, create a **Worker API key** and copy it.
3. Start a worker:
   ```bash
   PROJECT_API_KEY=sk_live_... docker compose --profile workers up worker
   ```
4. (Optional, for recurring/cron jobs and delayed-job promotion) start the scheduler:
   ```bash
   docker compose up scheduler
   ```

Workers aren't started by plain `docker compose up` because registering one requires an API
key that doesn't exist until you've created a project through the dashboard — see
[`docs/DESIGN_DECISIONS.md`](docs/DESIGN_DECISIONS.md) for why workers authenticate this way at
all, and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full request flow.

> **Verified with Docker.** `docker compose up postgres api scheduler frontend` plus
> `docker compose --profile workers up worker` were run end-to-end: Postgres → Alembic
> migrations → API → scheduler → frontend all start cleanly with correct health-check-gated
> startup ordering, and a containerized worker registered, claimed, executed, and completed a
> real job, then shut down gracefully on `docker compose stop` (SIGTERM → drain → shutdown).
> One real bug was caught and fixed in the process: `scheduler` originally only waited on
> Postgres being healthy, not on the API's migrations finishing, causing a one-time race on cold
> start (harmless — the loop catches and logs the error rather than crashing — but fixed
> properly by adding a `/healthz`-based healthcheck to `api` and gating `scheduler`/`frontend`/
> `worker` on it).

## Local development (without Docker)

Requires Python 3.12+, Node 20+, and a running PostgreSQL instance.

**Backend:**
```bash
cd backend
python -m venv venv
./venv/Scripts/activate        # source venv/bin/activate on macOS/Linux
pip install -r requirements.txt

cp .env.example .env           # then edit DATABASE_URL to point at your Postgres
alembic upgrade head
uvicorn app.main:app --reload  # http://localhost:8000
```

In separate terminals, once you've created a project/queue/API key via the API or dashboard:
```bash
# Worker
cd backend && PROJECT_API_KEY=sk_live_... SCHEDULER_API_URL=http://localhost:8000 \
  python -m app.worker.run_worker

# Scheduler (only needed for recurring/cron jobs)
cd backend && python -m app.scheduler.run_scheduler
```

**Frontend:**
```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_URL, defaults to http://localhost:8000
npm run dev             # http://localhost:5173
```

## Running tests

```bash
cd backend
# Tests run against a real Postgres database (SELECT ... FOR UPDATE SKIP LOCKED and native
# enums don't exist in SQLite, and those are exactly the properties worth testing here).
createdb scheduler_test   # or: psql -c "CREATE DATABASE scheduler_test"
pytest tests/ -v
```

25 tests covering auth, RBAC boundaries, all 5 job creation modes, pagination/idempotency, the
full worker lifecycle (start → complete / fail → retry-with-backoff → dead letter → retry),
queue concurrency limits, pause/resume, and — the one that matters most for a scheduler —
concurrent workers racing for the same jobs never double-claim
(`tests/test_claim_concurrency.py`).

## Project structure

```
backend/
  app/
    api/routes/       REST endpoints (auth, projects, queues, jobs, workers, scheduled-jobs, dead-letter)
    core/              security (JWT/API keys), auth dependencies, structured exceptions
    models/            SQLAlchemy ORM models (one file per entity)
    schemas/           Pydantic request/response models
    services/          business logic: atomic claim, retry backoff, job lifecycle transitions
    worker/            standalone worker process (run_worker.py) + demo handler registry
    scheduler/         standalone scheduler process (run_scheduler.py): fires due cron jobs
  alembic/             DB migrations
  tests/               pytest suite (integration, against real Postgres)
frontend/
  src/
    api/               typed API client
    pages/             Login, Projects, ProjectDetail, QueueDetail, JobDetail
    components/ui/     shared design-system primitives (Button, Input, Panel, SectionLabel)
    hooks/usePolling.ts
docs/                  architecture, ER diagram, API reference, design decisions
docker-compose.yml
```

## Demo job handlers

The worker ships with a small handler registry (`app/worker/handlers.py`) for exercising the
system without inventing a business domain: `log_message`, `sleep` (takes `{"seconds": N}`),
`http_request` (takes `{"url": ..., "method": ...}`), and `fail_randomly` (fails unless payload
includes `{"succeed": true}` — useful for watching the retry/DLQ path in the dashboard).
