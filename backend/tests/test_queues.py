import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import OrgRole, OrganizationMember
from app.models.user import User
from app.core.security import hash_password


async def test_create_queue_with_retry_policy(client: AsyncClient, auth_headers: dict, project_id: str):
    resp = await client.post(
        f"/api/v1/projects/{project_id}/queues",
        json={
            "name": "emails",
            "priority": 5,
            "max_concurrency": 3,
            "retry_policy": {"name": "r", "strategy": "linear", "max_attempts": 4, "base_delay_seconds": 5},
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["priority"] == 5
    assert body["default_retry_policy_id"] is not None


async def test_pause_and_resume_queue(client: AsyncClient, auth_headers: dict, queue_id: str):
    paused = await client.post(f"/api/v1/queues/{queue_id}/pause", headers=auth_headers)
    assert paused.json()["is_paused"] is True

    resumed = await client.post(f"/api/v1/queues/{queue_id}/resume", headers=auth_headers)
    assert resumed.json()["is_paused"] is False


async def test_stats_reflect_job_counts(client: AsyncClient, auth_headers: dict, queue_id: str):
    for _ in range(3):
        await client.post(
            f"/api/v1/queues/{queue_id}/jobs",
            json={"name": "log_message", "job_type": "immediate", "payload": {}},
            headers=auth_headers,
        )
    stats = await client.get(f"/api/v1/queues/{queue_id}/stats", headers=auth_headers)
    assert stats.json()["queued"] == 3


async def test_member_role_cannot_create_queue(client: AsyncClient, project_id: str, db_session: AsyncSession):
    """A user with only MEMBER role in the org should be forbidden from admin-level actions."""
    member = User(email="member@example.com", hashed_password=hash_password("password123"), full_name="Member")
    db_session.add(member)
    await db_session.flush()

    from app.models.project import Project

    project = await db_session.get(Project, uuid.UUID(project_id))
    db_session.add(OrganizationMember(organization_id=project.organization_id, user_id=member.id, role=OrgRole.MEMBER))
    await db_session.commit()

    login = await client.post("/api/v1/auth/login", json={"email": "member@example.com", "password": "password123"})
    member_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.post(
        f"/api/v1/projects/{project_id}/queues",
        json={"name": "blocked", "priority": 0, "max_concurrency": 1},
        headers=member_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "permission_denied"
