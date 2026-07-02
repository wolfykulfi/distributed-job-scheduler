"""Demo handler registry. A real deployment would register domain-specific handlers here;
the scheduler itself is domain-agnostic and only knows how to look a name up and call it.
"""

import asyncio
import random
from typing import Awaitable, Callable

import httpx

Handler = Callable[[dict], Awaitable[dict | None]]

_REGISTRY: dict[str, Handler] = {}


def handler(name: str):
    def decorator(fn: Handler) -> Handler:
        _REGISTRY[name] = fn
        return fn

    return decorator


def get_handler(name: str) -> Handler:
    if name not in _REGISTRY:
        raise KeyError(f"No handler registered for job name '{name}'")
    return _REGISTRY[name]


@handler("log_message")
async def log_message(payload: dict) -> dict:
    return {"logged": payload.get("text", "")}


@handler("sleep")
async def sleep_handler(payload: dict) -> dict:
    seconds = float(payload.get("seconds", 1))
    await asyncio.sleep(seconds)
    return {"slept_seconds": seconds}


@handler("http_request")
async def http_request(payload: dict) -> dict:
    url = payload["url"]
    method = payload.get("method", "GET")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(method, url)
        return {"status_code": response.status_code}


@handler("fail_randomly")
async def fail_randomly(payload: dict) -> dict:
    """Demo handler for exercising the retry/DLQ path; fails unless forced to succeed."""
    if not payload.get("succeed", False):
        raise RuntimeError(payload.get("message", "Simulated failure"))
    return {"ok": True}
