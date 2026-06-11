#!/usr/bin/env python3
"""
Start the CodeReview Agent review worker.

The worker pops delivery IDs from the Redis review queue (BLPOP) and runs the
LangGraph review pipeline for each one.  Press Ctrl+C for graceful shutdown.

    cd backend
    python scripts/run_worker.py

Environment
-----------
Reads configuration from backend/.env (or environment variables).
Redis and the backend services must be reachable (docker compose up redis).
"""
import asyncio
import logging
import signal
import sys
from pathlib import Path

# Ensure the backend package root is importable when running as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Trigger settings validation early so misconfiguration is obvious at startup.
import os  # noqa: E402
os.environ.setdefault("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))

from app.workers.review_worker import ReviewWorker  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    worker = ReviewWorker()

    # asyncio.get_running_loop() is the correct call inside an async function
    # (get_event_loop() is deprecated in Python 3.10+ when a loop is already running).
    loop = asyncio.get_running_loop()

    def _on_signal() -> None:
        worker.stop()

    # Register SIGINT / SIGTERM handlers for graceful shutdown.
    # add_signal_handler is not available on Windows; fall through to the
    # KeyboardInterrupt handler below in that case.
    try:
        loop.add_signal_handler(signal.SIGINT, _on_signal)
        loop.add_signal_handler(signal.SIGTERM, _on_signal)
    except (NotImplementedError, AttributeError):
        # Windows: rely on KeyboardInterrupt reaching the except clause below.
        pass

    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("[Worker] KeyboardInterrupt received — shutting down")
        worker.stop()

    logger.info("[Worker] Exited")


if __name__ == "__main__":
    asyncio.run(main())
