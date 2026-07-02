from httpx import AsyncClient


async def test_dependent_job_not_claimable_until_dependency_completes(
    client: AsyncClient, auth_headers: dict, queue_id: str, worker_token: str
):
    job_a = (
        await client.post(
            f"/api/v1/queues/{queue_id}/jobs",
            json={"name": "log_message", "job_type": "immediate", "payload": {}},
            headers=auth_headers,
        )
    ).json()

    job_b = (
        await client.post(
            f"/api/v1/queues/{queue_id}/jobs",
            json={"name": "log_message", "job_type": "immediate", "payload": {}, "depends_on": [job_a["id"]]},
            headers=auth_headers,
        )
    ).json()

    # Poll enough slots for both -- only A (no unmet deps) should come back.
    polled = (
        await client.post(
            "/api/v1/workers/poll", json={"max_jobs": 10}, headers={"Authorization": f"Bearer {worker_token}"}
        )
    ).json()
    polled_ids = {j["id"] for j in polled}
    assert job_a["id"] in polled_ids
    assert job_b["id"] not in polled_ids

    # Complete A.
    worker_headers = {"Authorization": f"Bearer {worker_token}"}
    await client.post(f"/api/v1/jobs/{job_a['id']}/start", headers=worker_headers)
    await client.post(f"/api/v1/jobs/{job_a['id']}/complete", json={"result": None}, headers=worker_headers)

    # B is now claimable.
    polled_again = (
        await client.post("/api/v1/workers/poll", json={"max_jobs": 10}, headers=worker_headers)
    ).json()
    assert job_b["id"] in {j["id"] for j in polled_again}


async def test_dependencies_endpoint_reports_status(client: AsyncClient, auth_headers: dict, queue_id: str):
    job_a = (
        await client.post(
            f"/api/v1/queues/{queue_id}/jobs",
            json={"name": "log_message", "job_type": "immediate", "payload": {}},
            headers=auth_headers,
        )
    ).json()
    job_b = (
        await client.post(
            f"/api/v1/queues/{queue_id}/jobs",
            json={"name": "log_message", "job_type": "immediate", "payload": {}, "depends_on": [job_a["id"]]},
            headers=auth_headers,
        )
    ).json()

    deps = (await client.get(f"/api/v1/jobs/{job_b['id']}/dependencies", headers=auth_headers)).json()
    assert len(deps) == 1
    assert deps[0]["job_id"] == job_a["id"]
    assert deps[0]["status"] == "queued"


async def test_depends_on_unknown_job_rejected(client: AsyncClient, auth_headers: dict, queue_id: str):
    import uuid

    resp = await client.post(
        f"/api/v1/queues/{queue_id}/jobs",
        json={"name": "log_message", "job_type": "immediate", "payload": {}, "depends_on": [str(uuid.uuid4())]},
        headers=auth_headers,
    )
    assert resp.status_code == 422
