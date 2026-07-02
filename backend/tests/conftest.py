import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models  # noqa: F401 -- registers all tables on Base.metadata
from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "postgresql+asyncpg://postgres@localhost:5433/scheduler_test"


@pytest_asyncio.fixture
async def db_engine():
    """Fresh engine per test function -- keeps every asyncpg connection bound to that test's
    own event loop, and gives each test a clean schema without cross-test leakage."""
    engine = create_async_engine(TEST_DATABASE_URL, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_local = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_local() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine):
    session_local = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_local() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict:
    """Registers a fresh user + org and returns Authorization headers."""
    import uuid

    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": "Test User", "organization_name": "TestOrg"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def project_id(client: AsyncClient, auth_headers: dict) -> str:
    orgs = (await client.get("/api/v1/organizations", headers=auth_headers)).json()
    resp = await client.post(
        f"/api/v1/organizations/{orgs[0]['id']}/projects", json={"name": "Test Project"}, headers=auth_headers
    )
    return resp.json()["id"]


@pytest_asyncio.fixture
async def queue_id(client: AsyncClient, auth_headers: dict, project_id: str) -> str:
    resp = await client.post(
        f"/api/v1/projects/{project_id}/queues",
        json={"name": "default", "priority": 0, "max_concurrency": 10},
        headers=auth_headers,
    )
    return resp.json()["id"]


@pytest_asyncio.fixture
async def worker_token(client: AsyncClient, auth_headers: dict, project_id: str) -> str:
    key_resp = await client.post(
        f"/api/v1/projects/{project_id}/api-keys", json={"name": "test-worker-key"}, headers=auth_headers
    )
    raw_key = key_resp.json()["api_key"]
    reg_resp = await client.post(
        "/api/v1/workers/register",
        json={"hostname": "test-host", "pid": 1, "concurrency": 10},
        headers={"X-API-Key": raw_key},
    )
    return reg_resp.json()["token"]
