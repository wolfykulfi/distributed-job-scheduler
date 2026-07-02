"""Standalone worker process entrypoint: `python -m app.worker.run_worker`.

Registers with the API using a project API key, then loops: poll for as many jobs as it has
free concurrency slots for, execute them concurrently (bounded by a semaphore), report
outcomes, and heartbeat on a separate timer. SIGINT/SIGTERM trigger a graceful drain: stop
polling, let in-flight jobs finish (bounded wait), then report shutdown.
"""

import asyncio
import logging
import os
import signal
import socket
import traceback

from app.config import settings
from app.worker.client import SchedulerClient
from app.worker.handlers import get_handler

logger = logging.getLogger("worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class Worker:
    def __init__(self) -> None:
        self.base_url = os.environ.get("SCHEDULER_API_URL", "http://localhost:8000")
        self.api_key = os.environ["PROJECT_API_KEY"]
        self.concurrency = int(os.environ.get("WORKER_CONCURRENCY", settings.worker_default_concurrency))
        self.poll_interval = float(os.environ.get("WORKER_POLL_INTERVAL", settings.worker_poll_interval_seconds))
        self.heartbeat_interval = float(
            os.environ.get("WORKER_HEARTBEAT_INTERVAL", settings.worker_heartbeat_interval_seconds)
        )
        self.client = SchedulerClient(self.base_url, project_api_key=self.api_key)
        self.semaphore = asyncio.Semaphore(self.concurrency)
        self.active_jobs = 0
        self.shutting_down = False
        self.tasks: set[asyncio.Task] = set()

    async def run(self) -> None:
        await self.client.register(socket.gethostname(), os.getpid(), self.concurrency)
        logger.info("Registered worker %s (concurrency=%d)", self.client.worker_id, self.concurrency)

        self._install_signal_handlers()
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        try:
            while not self.shutting_down:
                available = self.concurrency - self.active_jobs
                if available > 0:
                    jobs = await self.client.poll(max_jobs=available)
                    for job in jobs:
                        self.active_jobs += 1
                        task = asyncio.create_task(self._execute(job))
                        self.tasks.add(task)
                        task.add_done_callback(self.tasks.discard)
                await asyncio.sleep(self.poll_interval)
        finally:
            heartbeat_task.cancel()
            if self.tasks:
                logger.info("Draining: waiting for %d in-flight job(s) to finish...", len(self.tasks))
                await asyncio.wait(self.tasks, timeout=60)
            await self.client.shutdown()
            await self.client.close()
            logger.info("Worker shut down cleanly")

    def _install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.ensure_future(self._begin_shutdown()))
            except (NotImplementedError, ValueError, OSError):
                # Windows' default ProactorEventLoop doesn't support add_signal_handler;
                # fall back to signal.signal (works reliably for SIGINT / Ctrl+C there).
                signal.signal(sig, lambda *_: asyncio.ensure_future(self._begin_shutdown()))

    async def _begin_shutdown(self) -> None:
        if self.shutting_down:
            return
        logger.info("Shutdown signal received; draining (no new jobs will be claimed)...")
        self.shutting_down = True
        try:
            await self.client.drain()
        except Exception:
            logger.warning("Failed to notify server of drain", exc_info=True)

    async def _heartbeat_loop(self) -> None:
        while True:
            try:
                await self.client.heartbeat(self.active_jobs)
            except Exception:
                logger.warning("Heartbeat failed", exc_info=True)
            await asyncio.sleep(self.heartbeat_interval)

    async def _execute(self, job: dict) -> None:
        async with self.semaphore:
            job_id = job["id"]
            try:
                await self.client.start_job(job_id)
                await self._safe_log(job_id, "info", f"Claimed by {socket.gethostname()}, starting execution")
                handler = get_handler(job["name"])
                result = await handler(job["payload"])
                await self.client.complete_job(job_id, result)
                await self._safe_log(job_id, "info", "Execution completed successfully")
                logger.info("Job %s (%s) completed", job_id, job["name"])
            except Exception as exc:
                await self._safe_log(job_id, "error", f"Execution failed: {exc}")
                logger.warning("Job %s (%s) failed: %s", job_id, job["name"], exc)
                await self.client.fail_job(job_id, str(exc), traceback.format_exc())
            finally:
                self.active_jobs -= 1

    async def _safe_log(self, job_id: str, level: str, message: str) -> None:
        # Logging is best-effort: a log line failing to write should never fail the job itself.
        try:
            await self.client.log(job_id, level, message)
        except Exception:
            logger.debug("Failed to write log line for job %s", job_id, exc_info=True)


def main() -> None:
    asyncio.run(Worker().run())


if __name__ == "__main__":
    main()
