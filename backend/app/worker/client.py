"""Thin async HTTP client wrapping the worker-facing REST endpoints."""

import httpx


class SchedulerClient:
    def __init__(self, base_url: str, project_api_key: str | None = None, worker_token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.project_api_key = project_api_key
        self.worker_token = worker_token
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30)

    async def close(self) -> None:
        await self._client.aclose()

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.worker_token}"}

    async def register(self, hostname: str, pid: int, concurrency: int) -> None:
        resp = await self._client.post(
            "/api/v1/workers/register",
            headers={"X-API-Key": self.project_api_key},
            json={"hostname": hostname, "pid": pid, "concurrency": concurrency},
        )
        resp.raise_for_status()
        data = resp.json()
        self.worker_id = data["worker_id"]
        self.worker_token = data["token"]

    async def poll(self, max_jobs: int) -> list[dict]:
        resp = await self._client.post(
            "/api/v1/workers/poll", headers=self._auth_headers(), json={"max_jobs": max_jobs}
        )
        resp.raise_for_status()
        return resp.json()

    async def heartbeat(self, active_job_count: int) -> None:
        resp = await self._client.post(
            "/api/v1/workers/heartbeat", headers=self._auth_headers(), json={"active_job_count": active_job_count}
        )
        resp.raise_for_status()

    async def drain(self) -> None:
        resp = await self._client.post("/api/v1/workers/drain", headers=self._auth_headers())
        resp.raise_for_status()

    async def shutdown(self) -> None:
        resp = await self._client.post("/api/v1/workers/shutdown", headers=self._auth_headers())
        resp.raise_for_status()

    async def start_job(self, job_id: str) -> dict:
        resp = await self._client.post(f"/api/v1/jobs/{job_id}/start", headers=self._auth_headers())
        resp.raise_for_status()
        return resp.json()

    async def complete_job(self, job_id: str, result: dict | None) -> None:
        resp = await self._client.post(
            f"/api/v1/jobs/{job_id}/complete", headers=self._auth_headers(), json={"result": result}
        )
        resp.raise_for_status()

    async def fail_job(self, job_id: str, error_message: str, error_stacktrace: str | None) -> None:
        resp = await self._client.post(
            f"/api/v1/jobs/{job_id}/fail",
            headers=self._auth_headers(),
            json={"error_message": error_message, "error_stacktrace": error_stacktrace},
        )
        resp.raise_for_status()

    async def log(self, job_id: str, level: str, message: str) -> None:
        resp = await self._client.post(
            f"/api/v1/jobs/{job_id}/logs", headers=self._auth_headers(), json={"level": level, "message": message}
        )
        resp.raise_for_status()
