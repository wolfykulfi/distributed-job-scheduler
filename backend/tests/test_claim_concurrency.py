"""Proves the core reliability guarantee: concurrent pollers never claim the same job twice.

Uses the real HTTP layer (not calling claim_service directly) with asyncio.gather so requests
genuinely overlap, each on its own DB connection/transaction -- this is what actually exercises
`SELECT ... FOR UPDATE SKIP LOCKED` under contention rather than just testing the SQL in isolation.
"""

import asyncio

from httpx import AsyncClient


async def _register_worker(client: AsyncClient, project_id: str, auth_headers: dict, name: str) -> str:
    key_resp = await client.post(f"/api/v1/projects/{project_id}/api-keys", json={"name": name}, headers=auth_headers)
    raw_key = key_resp.json()["api_key"]
    reg_resp = await client.post(
        "/api/v1/workers/register",
        json={"hostname": name, "pid": 1, "concurrency": 20},
        headers={"X-API-Key": raw_key},
    )
    return reg_resp.json()["token"]


async def test_concurrent_pollers_never_claim_the_same_job(client: AsyncClient, auth_headers: dict, project_id: str):
    queue = await client.post(
        f"/api/v1/projects/{project_id}/queues",
        json={"name": "contended", "priority": 0, "max_concurrency": 100},
        headers=auth_headers,
    )
    queue_id = queue.json()["id"]

    job_count = 30
    for i in range(job_count):
        await client.post(
            f"/api/v1/queues/{queue_id}/jobs",
            json={"name": "log_message", "job_type": "immediate", "payload": {"i": i}},
            headers=auth_headers,
        )

    worker_count = 6
    tokens = [await _register_worker(client, project_id, auth_headers, f"worker-{i}") for i in range(worker_count)]

    async def poll(token: str) -> list[str]:
        resp = await client.post(
            "/api/v1/workers/poll", json={"max_jobs": job_count}, headers={"Authorization": f"Bearer {token}"}
        )
        return [job["id"] for job in resp.json()]

    results = await asyncio.gather(*(poll(t) for t in tokens))

    all_claimed_ids = [job_id for worker_result in results for job_id in worker_result]

    assert len(all_claimed_ids) == job_count, "every job should be claimed exactly once across all workers"
    assert len(set(all_claimed_ids)) == job_count, "no job should be claimed by more than one worker"
