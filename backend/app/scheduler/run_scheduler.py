"""Standalone scheduler process entrypoint: `python -m app.scheduler.run_scheduler`."""

import asyncio
import logging
import signal

from app.config import settings
from app.database import AsyncSessionLocal
from app.scheduler.scheduler_loop import fire_due_scheduled_jobs

logger = logging.getLogger("scheduler")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def main() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, ValueError, OSError):
            signal.signal(sig, lambda *_: stop.set())

    logger.info("Scheduler started (poll interval=%.1fs)", settings.scheduler_poll_interval_seconds)
    while not stop.is_set():
        async with AsyncSessionLocal() as db:
            try:
                fired = await fire_due_scheduled_jobs(db)
                if fired:
                    logger.info("Fired %d recurring job instance(s)", fired)
            except Exception:
                logger.exception("Error while firing scheduled jobs")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.scheduler_poll_interval_seconds)
        except asyncio.TimeoutError:
            pass
    logger.info("Scheduler stopped")


if __name__ == "__main__":
    asyncio.run(main())
