"""General-purpose distributed lock, built on Postgres advisory locks.

Separate from (and complementary to) the row-level `FOR UPDATE SKIP LOCKED` used for job
claiming -- this is for coarse-grained "only one of these should run at a time across the whole
fleet" cases, e.g. a periodic maintenance task that shouldn't run concurrently even if multiple
scheduler/API replicas are up. Session-level advisory locks are held for the lifetime of the DB
connection, so this must be used within a single `async with` block on one connection.
"""

import zlib
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _lock_key(name: str) -> int:
    """Postgres advisory locks are keyed by a 64-bit (here: 32-bit, plenty of keyspace for a
    handful of named locks) integer, not a string -- deterministically hash the name to one."""
    return zlib.crc32(name.encode())


@asynccontextmanager
async def try_advisory_lock(db: AsyncSession, name: str) -> AsyncIterator[bool]:
    """Attempts a non-blocking advisory lock. Yields True if acquired (and releases on exit),
    False if another session already holds it (caller should skip its critical section)."""
    key = _lock_key(name)
    acquired = (await db.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})).scalar()
    try:
        yield bool(acquired)
    finally:
        if acquired:
            await db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
