"""Live job-event push over WebSocket, backed by Postgres LISTEN/NOTIFY (see notify_service.py).

Kept alongside polling (usePolling.ts) rather than replacing it: if a client's WebSocket drops
or a proxy in front of the app doesn't support upgrades, the dashboard still works, just less
instantly. WS is a latency optimization here, not the only path to correctness.
"""

import asyncio
import json
import uuid

import asyncpg
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.security import decode_token
from app.database import AsyncSessionLocal, raw_asyncpg_dsn
from app.models.organization import OrganizationMember
from app.models.project import Project
from app.models.queue import Queue
from app.models.user import User
from app.services.notify_service import CHANNEL

router = APIRouter(tags=["websocket"])


async def _authorize(websocket: WebSocket, queue_id: uuid.UUID, token: str | None) -> bool:
    """Mirrors core/deps.py's user-auth + MEMBER-role check, adapted for a query-param token
    (browsers' native WebSocket API can't set an Authorization header)."""
    if not token:
        return False
    try:
        payload = decode_token(token)
    except ValueError:
        return False
    if payload.get("type") != "user":
        return False

    async with AsyncSessionLocal() as db:
        user = await db.get(User, uuid.UUID(payload["sub"]))
        if user is None or not user.is_active:
            return False
        queue = await db.get(Queue, queue_id)
        if queue is None:
            return False
        project = await db.get(Project, queue.project_id)
        if project is None:
            return False
        membership = await db.scalar(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == project.organization_id,
                OrganizationMember.user_id == user.id,
            )
        )
        return membership is not None


@router.websocket("/api/v1/ws/queues/{queue_id}")
async def queue_events(websocket: WebSocket, queue_id: uuid.UUID, token: str | None = None) -> None:
    if not await _authorize(websocket, queue_id, token):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    queue_id_str = str(queue_id)
    events: asyncio.Queue[str] = asyncio.Queue()

    def on_notify(_conn, _pid, _channel, payload: str) -> None:
        events.put_nowait(payload)

    conn = await asyncpg.connect(dsn=raw_asyncpg_dsn())
    await conn.add_listener(CHANNEL, on_notify)

    async def forward_events() -> None:
        while True:
            payload = await events.get()
            data = json.loads(payload)
            if data.get("queue_id") == queue_id_str:
                await websocket.send_json(data)

    async def watch_for_disconnect() -> None:
        while True:
            await websocket.receive_text()  # client sends nothing meaningful; just detects close

    forward_task = asyncio.create_task(forward_events())
    watch_task = asyncio.create_task(watch_for_disconnect())
    try:
        await asyncio.wait({forward_task, watch_task}, return_when=asyncio.FIRST_COMPLETED)
    except WebSocketDisconnect:
        pass
    finally:
        forward_task.cancel()
        watch_task.cancel()
        await conn.remove_listener(CHANNEL, on_notify)
        await conn.close()
