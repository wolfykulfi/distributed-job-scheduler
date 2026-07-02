"""Publishes job state-change events via Postgres NOTIFY, consumed by the WebSocket endpoint.

Called from inside the same transaction as the state change, *before* that transaction's
final commit -- Postgres only delivers a NOTIFY to listeners once its transaction actually
commits, so this gets exactly the right semantics for free: a listener never sees an event for
a change that gets rolled back, and always sees it exactly when the change becomes visible to
everyone else querying the table.
"""

import json
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

CHANNEL = "job_events"


async def notify_job_event(db: AsyncSession, queue_id: uuid.UUID, job_id: uuid.UUID, status: str) -> None:
    payload = json.dumps({"queue_id": str(queue_id), "job_id": str(job_id), "status": status})
    await db.execute(text("SELECT pg_notify(:channel, :payload)"), {"channel": CHANNEL, "payload": payload})
