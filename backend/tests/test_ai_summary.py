from httpx import AsyncClient

from app.config import settings


async def test_ai_summary_rejected_for_non_failed_execution(
    client: AsyncClient, auth_headers: dict, queue_id: str, worker_token: str
):
    job = (
        await client.post(
            f"/api/v1/queues/{queue_id}/jobs",
            json={"name": "log_message", "job_type": "immediate", "payload": {}},
            headers=auth_headers,
        )
    ).json()
    worker_headers = {"Authorization": f"Bearer {worker_token}"}
    await client.post("/api/v1/workers/poll", json={"max_jobs": 10}, headers=worker_headers)
    await client.post(f"/api/v1/jobs/{job['id']}/start", headers=worker_headers)
    await client.post(f"/api/v1/jobs/{job['id']}/complete", json={"result": None}, headers=worker_headers)

    execs = (await client.get(f"/api/v1/jobs/{job['id']}/executions", headers=auth_headers)).json()
    resp = await client.post(
        f"/api/v1/jobs/{job['id']}/executions/{execs[0]['id']}/ai-summary", headers=auth_headers
    )
    assert resp.status_code == 409


async def test_ai_summary_without_groq_key_returns_503(
    client: AsyncClient, auth_headers: dict, queue_id: str, worker_token: str, monkeypatch
):
    monkeypatch.setattr(settings, "groq_api_key", None)

    job = (
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
    worker_headers = {"Authorization": f"Bearer {worker_token}"}
    await client.post("/api/v1/workers/poll", json={"max_jobs": 10}, headers=worker_headers)
    await client.post(f"/api/v1/jobs/{job['id']}/start", headers=worker_headers)
    await client.post(
        f"/api/v1/jobs/{job['id']}/fail", json={"error_message": "boom"}, headers=worker_headers
    )

    execs = (await client.get(f"/api/v1/jobs/{job['id']}/executions", headers=auth_headers)).json()
    resp = await client.post(
        f"/api/v1/jobs/{job['id']}/executions/{execs[0]['id']}/ai-summary", headers=auth_headers
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "ai_summary_unavailable"
