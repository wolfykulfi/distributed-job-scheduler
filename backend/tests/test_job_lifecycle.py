import asyncio

from httpx import AsyncClient


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_full_success_lifecycle(client: AsyncClient, auth_headers: dict, queue_id: str, worker_token: str):
    created = await client.post(
        f"/api/v1/queues/{queue_id}/jobs",
        json={"name": "log_message", "job_type": "immediate", "payload": {"text": "hi"}},
        headers=auth_headers,
    )
    job_id = created.json()["id"]

    polled = await client.post("/api/v1/workers/poll", json={"max_jobs": 10}, headers=_headers(worker_token))
    assert len(polled.json()) == 1
    assert polled.json()[0]["id"] == job_id

    start = await client.post(f"/api/v1/jobs/{job_id}/start", headers=_headers(worker_token))
    assert start.status_code == 200
    assert start.json()["attempt_number"] == 1

    complete = await client.post(
        f"/api/v1/jobs/{job_id}/complete", json={"result": {"ok": True}}, headers=_headers(worker_token)
    )
    assert complete.status_code == 204

    final = await client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
    assert final.json()["status"] == "completed"

    executions = await client.get(f"/api/v1/jobs/{job_id}/executions", headers=auth_headers)
    assert len(executions.json()) == 1
    assert executions.json()[0]["status"] == "succeeded"


async def test_failure_retries_then_moves_to_dead_letter(
    client: AsyncClient, auth_headers: dict, queue_id: str, worker_token: str
):
    created = await client.post(
        f"/api/v1/queues/{queue_id}/jobs",
        json={
            "name": "fail_randomly",
            "job_type": "immediate",
            "payload": {},
            "retry_policy": {"name": "fast", "strategy": "fixed", "max_attempts": 2, "base_delay_seconds": 1},
        },
        headers=auth_headers,
    )
    job_id = created.json()["id"]

    # Attempt 1: fails, should be rescheduled for retry (not dead-lettered yet).
    polled = await client.post("/api/v1/workers/poll", json={"max_jobs": 10}, headers=_headers(worker_token))
    assert len(polled.json()) == 1
    await client.post(f"/api/v1/jobs/{job_id}/start", headers=_headers(worker_token))
    await client.post(
        f"/api/v1/jobs/{job_id}/fail", json={"error_message": "boom", "error_stacktrace": None}, headers=_headers(worker_token)
    )
    after_first_failure = await client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
    assert after_first_failure.json()["status"] == "scheduled"
    assert after_first_failure.json()["attempt_count"] == 1

    # base_delay_seconds=1 means it's eligible again shortly.
    await asyncio.sleep(1.2)

    # Attempt 2: fails again, exceeds max_attempts=2 -> dead letter.
    polled2 = await client.post("/api/v1/workers/poll", json={"max_jobs": 10}, headers=_headers(worker_token))
    assert len(polled2.json()) == 1
    await client.post(f"/api/v1/jobs/{job_id}/start", headers=_headers(worker_token))
    await client.post(
        f"/api/v1/jobs/{job_id}/fail", json={"error_message": "boom again", "error_stacktrace": None}, headers=_headers(worker_token)
    )

    final = await client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
    assert final.json()["status"] == "dead_letter"

    dlq = await client.get(f"/api/v1/queues/{queue_id}/dead-letter", headers=auth_headers)
    assert len(dlq.json()) == 1
    dlq_id = dlq.json()[0]["id"]

    retried = await client.post(f"/api/v1/dead-letter/{dlq_id}/retry", headers=auth_headers)
    assert retried.status_code == 200
    assert retried.json()["status"] == "queued"
    assert retried.json()["attempt_count"] == 0


async def test_queue_max_concurrency_limits_claims(
    client: AsyncClient, auth_headers: dict, project_id: str, worker_token: str
):
    queue = await client.post(
        f"/api/v1/projects/{project_id}/queues",
        json={"name": "limited", "priority": 0, "max_concurrency": 2},
        headers=auth_headers,
    )
    queue_id = queue.json()["id"]

    for _ in range(5):
        await client.post(
            f"/api/v1/queues/{queue_id}/jobs",
            json={"name": "log_message", "job_type": "immediate", "payload": {}},
            headers=auth_headers,
        )

    polled = await client.post("/api/v1/workers/poll", json={"max_jobs": 10}, headers=_headers(worker_token))
    assert len(polled.json()) == 2  # capped by max_concurrency, not max_jobs


async def test_paused_queue_claims_nothing(client: AsyncClient, auth_headers: dict, queue_id: str, worker_token: str):
    await client.post(
        f"/api/v1/queues/{queue_id}/jobs",
        json={"name": "log_message", "job_type": "immediate", "payload": {}},
        headers=auth_headers,
    )
    await client.post(f"/api/v1/queues/{queue_id}/pause", headers=auth_headers)

    polled = await client.post("/api/v1/workers/poll", json={"max_jobs": 10}, headers=_headers(worker_token))
    assert polled.json() == []
