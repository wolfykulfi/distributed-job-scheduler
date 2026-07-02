from httpx import AsyncClient


async def test_create_immediate_job(client: AsyncClient, auth_headers: dict, queue_id: str):
    resp = await client.post(
        f"/api/v1/queues/{queue_id}/jobs",
        json={"name": "log_message", "job_type": "immediate", "payload": {"text": "hi"}},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "queued"


async def test_delayed_job_is_scheduled_not_queued(client: AsyncClient, auth_headers: dict, queue_id: str):
    resp = await client.post(
        f"/api/v1/queues/{queue_id}/jobs",
        json={"name": "sleep", "job_type": "delayed", "delay_seconds": 60, "payload": {}},
        headers=auth_headers,
    )
    body = resp.json()
    assert body["status"] == "scheduled"
    assert body["scheduled_for"] is not None


async def test_delayed_job_without_delay_seconds_rejected(client: AsyncClient, auth_headers: dict, queue_id: str):
    resp = await client.post(
        f"/api/v1/queues/{queue_id}/jobs",
        json={"name": "sleep", "job_type": "delayed", "payload": {}},
        headers=auth_headers,
    )
    assert resp.status_code == 422


async def test_idempotency_key_conflict(client: AsyncClient, auth_headers: dict, queue_id: str):
    body = {"name": "log_message", "job_type": "immediate", "payload": {}, "idempotency_key": "order-123"}
    first = await client.post(f"/api/v1/queues/{queue_id}/jobs", json=body, headers=auth_headers)
    assert first.status_code == 201
    second = await client.post(f"/api/v1/queues/{queue_id}/jobs", json=body, headers=auth_headers)
    assert second.status_code == 409


async def test_batch_creates_grouped_jobs(client: AsyncClient, auth_headers: dict, queue_id: str):
    resp = await client.post(
        f"/api/v1/queues/{queue_id}/jobs/batch",
        json={
            "batch_name": "import",
            "name": "log_message",
            "items": [{"payload": {"i": 1}}, {"payload": {"i": 2}}, {"payload": {"i": 3}}],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["total_jobs"] == 3

    listing = await client.get(f"/api/v1/queues/{queue_id}/jobs?job_type=batch", headers=auth_headers)
    assert listing.json()["total"] == 3


async def test_list_jobs_pagination(client: AsyncClient, auth_headers: dict, queue_id: str):
    for i in range(5):
        await client.post(
            f"/api/v1/queues/{queue_id}/jobs",
            json={"name": "log_message", "job_type": "immediate", "payload": {"i": i}},
            headers=auth_headers,
        )
    page1 = await client.get(f"/api/v1/queues/{queue_id}/jobs?limit=2&offset=0", headers=auth_headers)
    page2 = await client.get(f"/api/v1/queues/{queue_id}/jobs?limit=2&offset=2", headers=auth_headers)
    assert len(page1.json()["items"]) == 2
    assert len(page2.json()["items"]) == 2
    assert page1.json()["total"] == 5
    assert {j["id"] for j in page1.json()["items"]}.isdisjoint({j["id"] for j in page2.json()["items"]})


async def test_cancel_queued_job(client: AsyncClient, auth_headers: dict, queue_id: str):
    created = await client.post(
        f"/api/v1/queues/{queue_id}/jobs",
        json={"name": "log_message", "job_type": "immediate", "payload": {}},
        headers=auth_headers,
    )
    job_id = created.json()["id"]
    cancelled = await client.post(f"/api/v1/jobs/{job_id}/cancel", headers=auth_headers)
    assert cancelled.json()["status"] == "cancelled"

    # Cancelling again should fail -- it's no longer in a cancellable state.
    second = await client.post(f"/api/v1/jobs/{job_id}/cancel", headers=auth_headers)
    assert second.status_code == 409
