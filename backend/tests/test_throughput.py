from httpx import AsyncClient


async def test_throughput_counts_completed_and_failed(
    client: AsyncClient, auth_headers: dict, queue_id: str, worker_token: str
):
    worker_headers = {"Authorization": f"Bearer {worker_token}"}

    ok_job = (
        await client.post(
            f"/api/v1/queues/{queue_id}/jobs",
            json={"name": "log_message", "job_type": "immediate", "payload": {}},
            headers=auth_headers,
        )
    ).json()
    bad_job = (
        await client.post(
            f"/api/v1/queues/{queue_id}/jobs",
            json={
                "name": "fail_randomly",
                "job_type": "immediate",
                "payload": {},
                "retry_policy": {"name": "once", "strategy": "fixed", "max_attempts": 1, "base_delay_seconds": 1},
            },
            headers=auth_headers,
        )
    ).json()

    claimed = (await client.post("/api/v1/workers/poll", json={"max_jobs": 10}, headers=worker_headers)).json()
    assert {j["id"] for j in claimed} == {ok_job["id"], bad_job["id"]}

    await client.post(f"/api/v1/jobs/{ok_job['id']}/start", headers=worker_headers)
    await client.post(f"/api/v1/jobs/{ok_job['id']}/complete", json={"result": None}, headers=worker_headers)

    await client.post(f"/api/v1/jobs/{bad_job['id']}/start", headers=worker_headers)
    await client.post(
        f"/api/v1/jobs/{bad_job['id']}/fail", json={"error_message": "boom"}, headers=worker_headers
    )

    resp = await client.get(f"/api/v1/queues/{queue_id}/throughput", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_completed"] == 1
    assert data["total_failed"] == 1
    assert data["health"] == "unhealthy"  # 1/2 = 50% error rate, at the unhealthy boundary (>= 50%)
    assert len(data["buckets"]) == 12  # 60min window / 5min buckets by default
    assert sum(b["completed"] for b in data["buckets"]) == 1
    assert sum(b["failed"] for b in data["buckets"]) == 1


async def test_throughput_idle_queue_reports_healthy(client: AsyncClient, auth_headers: dict, queue_id: str):
    resp = await client.get(f"/api/v1/queues/{queue_id}/throughput", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["health"] == "idle"
    assert data["total_completed"] == 0
    assert data["total_failed"] == 0
