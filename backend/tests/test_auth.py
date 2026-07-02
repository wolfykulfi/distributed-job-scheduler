from httpx import AsyncClient


async def test_register_and_me(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "full_name": "A", "organization_name": "Org"},
    )
    assert resp.status_code == 201
    token = resp.json()["access_token"]

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "a@example.com"


async def test_duplicate_email_registration_conflicts(client: AsyncClient):
    body = {"email": "dup@example.com", "password": "password123", "full_name": "A", "organization_name": "Org"}
    first = await client.post("/api/v1/auth/register", json=body)
    assert first.status_code == 201
    second = await client.post("/api/v1/auth/register", json=body)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


async def test_login_wrong_password_rejected(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "b@example.com", "password": "password123", "full_name": "B", "organization_name": "Org"},
    )
    resp = await client.post("/api/v1/auth/login", json={"email": "b@example.com", "password": "wrong"})
    assert resp.status_code == 401


async def test_unauthenticated_request_rejected(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
