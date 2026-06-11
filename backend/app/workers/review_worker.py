"""
Review worker.

Consumes delivery IDs from the Redis review queue (BLPOP) and executes the
LangGraph review pipeline for each one.

Reliability guarantees
----------------------
  - Per-job failure isolation: a failed review never crashes the worker.
  - Job timeout: each graph execution is wrapped in asyncio.wait_for(); a
    hung Groq or GitHub connection cannot block the worker indefinitely.
  - Exponential backoff: Redis errors back off from 1 s → 2 → 4 → 8 → 16 → 30 s
    before resetting on the next successful operation.
  - Worker heartbeat: a background coroutine writes to github:worker:heartbeat
    every 10 seconds (TTL 30 s).  Absence of the key means the worker is dead.

Usage (via run_worker.py):
    cd backend
    python scripts/run_worker.py
"""
import asyncio
import json
import logging
from datetime import UTC, datetime

from app.core.config import settings
from app.core.constants import REVIEW_QUEUE_KEY, WORKER_HEARTBEAT_KEY
from app.graph.review_graph import run_review_graph
from app.services.comment_dedup import is_already_reviewed, mark_as_reviewed
from app.services.github_review_builder import build_review_submission
from app.services.github_review_client import submit_review
from app.services.graph_state_store import get_graph_state, mark_graph_state_failed
from app.services.redis_service import get_redis_client
from app.services.review_result_store import get_review_result
from app.services.review_submission_store import get_review_submission, save_review_submission

logger = logging.getLogger(__name__)

# BLPOP blocks for at most this many seconds before returning None.
# Keeps the shutdown latency bounded without busy-polling.
_BLPOP_TIMEOUT = 5

# Heartbeat cadence and TTL (TTL > interval ensures no false-dead gaps).
_HEARTBEAT_INTERVAL = 10   # seconds between writes
_HEARTBEAT_TTL = 30        # Redis key TTL — expires if worker dies

# Exponential backoff sequence (seconds) for Redis errors.
# Capped at 30 s; resets to index 0 on the first successful loop iteration.
_BACKOFF_SEQUENCE = (1, 2, 4, 8, 16, 30)


class ReviewWorker:
    """
    Long-running async worker that pops jobs from the review queue and runs
    the LangGraph review pipeline for each delivery ID.
    """

    def __init__(self) -> None:
        self._running = False
        self._backoff_idx = 0  # index into _BACKOFF_SEQUENCE

    def stop(self) -> None:
        """Signal the run loop to exit after the current BLPOP timeout."""
        logger.info("[Worker] Stop requested")
        self._running = False

    async def run(self) -> None:
        """
        Start the event loop.  Blocks until stop() is called or the process
        receives a termination signal.

        A background heartbeat task runs concurrently; it is cancelled cleanly
        when the main loop exits.
        """
        self._running = True
        logger.info(
            "[Worker] Started — queue=%s timeout=%ds",
            REVIEW_QUEUE_KEY,
            settings.REVIEW_JOB_TIMEOUT_SECONDS,
        )

        heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        try:
            while self._running:
                try:
                    await self._process_one()
                    # Successful iteration (job processed or BLPOP timeout) —
                    # reset the Redis error backoff counter.
                    self._backoff_idx = 0
                except Exception as exc:  # noqa: BLE001
                    wait = _BACKOFF_SEQUENCE[
                        min(self._backoff_idx, len(_BACKOFF_SEQUENCE) - 1)
                    ]
                    logger.error(
                        "[Worker] Error in main loop (backing off %ds): %s",
                        wait, exc,
                    )
                    self._backoff_idx = min(
                        self._backoff_idx + 1, len(_BACKOFF_SEQUENCE) - 1
                    )
                    await asyncio.sleep(wait)
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

        logger.info("[Worker] Stopped")

    async def _process_one(self) -> None:
        """
        Block for up to _BLPOP_TIMEOUT seconds waiting for a job.

        On timeout, returns immediately so the loop can re-check self._running.
        On success, runs the full review graph with a configurable timeout.
        """
        client = await get_redis_client()

        # BLPOP returns (queue_name, value) or None on timeout.
        # decode_responses=True guarantees value is already a str.
        result = await client.blpop([REVIEW_QUEUE_KEY], timeout=_BLPOP_TIMEOUT)
        if result is None:
            return  # idle timeout — loop will re-check _running

        _, delivery_id = result
        logger.info("[Worker] Job received: delivery_id=%s", delivery_id)

        try:
            final_state = await asyncio.wait_for(
                run_review_graph(delivery_id),
                timeout=settings.REVIEW_JOB_TIMEOUT_SECONDS,
            )
            status = final_state.get("status", "unknown")
            if status == "completed":
                logger.info("[Worker] Job completed: delivery_id=%s", delivery_id)
                # Phase 6 — build and submit the GitHub review.
                # Failures here are isolated: they never affect the backoff
                # counter (already reset above) or the review status.
                submission_meta = await self._submit_review(delivery_id)
                await self._persist_review(delivery_id, submission_meta)
            else:
                logger.warning(
                    "[Worker] Job ended status=%s: delivery_id=%s error=%s",
                    status, delivery_id, final_state.get("error"),
                )

        except asyncio.TimeoutError:
            logger.error(
                "[Worker] Job timed out after %ds: delivery_id=%s",
                settings.REVIEW_JOB_TIMEOUT_SECONDS, delivery_id,
            )
            try:
                await mark_graph_state_failed(
                    delivery_id,
                    f"Review job timed out after {settings.REVIEW_JOB_TIMEOUT_SECONDS}s",
                )
            except Exception as save_exc:  # noqa: BLE001
                logger.warning(
                    "[Worker] Could not save timeout state: delivery_id=%s error=%s",
                    delivery_id, save_exc,
                )
            await self._persist_review(delivery_id, None)

        except Exception as exc:  # noqa: BLE001
            # Graph-level error (outside node code) — the job is dropped but
            # the worker continues.  Node failures are captured in state already.
            logger.error(
                "[Worker] Graph execution error: delivery_id=%s error=%s",
                delivery_id, exc,
            )
            await self._persist_review(delivery_id, None)

    async def _submit_review(self, delivery_id: str) -> dict | None:
        """
        Build a GitHub review payload and either store it (dry-run) or post it.

        Returns a metadata dict on success, None on any failure or early exit.
        The dict contains: dry_run, submitted_to_github, github_review_id.

        This method swallows all exceptions so a submission failure never
        crashes the worker or affects the main job's status.

        Flow
        ----
        1. Load ReviewResult and graph state from Redis.
        2. Check dedup lock — skip silently if already submitted.
        3. Build ReviewSubmission via github_review_builder.
        4a. Dry-run (GITHUB_DRY_RUN=true):  store payload, log, set dedup lock.
        4b. Live (GITHUB_DRY_RUN=false): post to GitHub API, store payload,
            set dedup lock.
        """
        try:
            result = await get_review_result(delivery_id)
            if result is None:
                logger.error(
                    "[Worker] ReviewResult missing — cannot submit review: delivery_id=%s",
                    delivery_id,
                )
                return None

            graph_state = await get_graph_state(delivery_id)
            if graph_state is None:
                logger.error(
                    "[Worker] Graph state missing — cannot submit review: delivery_id=%s",
                    delivery_id,
                )
                return None

            if await is_already_reviewed(delivery_id):
                logger.info(
                    "[Worker] Review already submitted (dedup lock hit): delivery_id=%s",
                    delivery_id,
                )
                return None

            submission = build_review_submission(result, graph_state)

            if settings.GITHUB_DRY_RUN:
                await save_review_submission(delivery_id, submission)
                await mark_as_reviewed(delivery_id)
                logger.info(
                    "[Worker] Dry-run: review payload stored: delivery_id=%s "
                    "event=%s inline_comments=%d",
                    delivery_id, submission.event, len(submission.comments),
                )
                return {
                    "dry_run": True,
                    "submitted_to_github": False,
                    "github_review_id": None,
                }
            else:
                installation_id = graph_state.get("installation_id")
                if not installation_id:
                    logger.error(
                        "[Worker] installation_id missing from graph state: delivery_id=%s",
                        delivery_id,
                    )
                    return None
                api_response = await submit_review(
                    owner=submission.owner,
                    repo=submission.repo,
                    pr_number=submission.pr_number,
                    installation_id=int(installation_id),
                    review_submission=submission,
                )
                await save_review_submission(delivery_id, submission)
                await mark_as_reviewed(delivery_id)
                github_review_id: int | None = None
                if isinstance(api_response, dict):
                    github_review_id = api_response.get("id")
                logger.info(
                    "[Worker] Review posted to GitHub: delivery_id=%s "
                    "event=%s inline_comments=%d review_id=%s",
                    delivery_id, submission.event, len(submission.comments),
                    github_review_id,
                )
                return {
                    "dry_run": False,
                    "submitted_to_github": True,
                    "github_review_id": github_review_id,
                }

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "[Worker] Failed to submit review: delivery_id=%s error=%s",
                delivery_id, exc,
            )
            return None

    async def _persist_review(
        self,
        delivery_id: str,
        submission_meta: dict | None,
    ) -> None:
        """
        Persist the completed (or failed) review run to PostgreSQL.

        submission_meta is the dict returned by _submit_review():
            {"dry_run": bool, "submitted_to_github": bool, "github_review_id": int|None}
        Pass None for failed/timed-out jobs where submission was never attempted.

        Swallows all exceptions so a DB failure never crashes the worker or
        affects the Redis-based review status visible to callers.
        """
        try:
            from app.services.persistence_service import persist_review_run  # noqa: PLC0415

            graph_state = await get_graph_state(delivery_id)
            if graph_state is None:
                logger.warning(
                    "[Worker] Graph state missing, skipping persistence: delivery_id=%s",
                    delivery_id,
                )
                return

            result = await get_review_result(delivery_id)
            submission = await get_review_submission(delivery_id)

            meta = submission_meta or {}
            summary = await persist_review_run(
                delivery_id=delivery_id,
                graph_state=graph_state,
                review_result=result,
                review_submission=submission,
                dry_run=meta.get("dry_run", settings.GITHUB_DRY_RUN),
                submitted_to_github=meta.get("submitted_to_github", False),
                github_review_id=meta.get("github_review_id"),
            )
            logger.info("[Worker] Persisted to DB: %s", summary)

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "[Worker] Failed to persist review: delivery_id=%s error=%s",
                delivery_id, exc,
            )

    async def _heartbeat_loop(self) -> None:
        """
        Write a heartbeat record to Redis every _HEARTBEAT_INTERVAL seconds.

        Failure to write is logged as a warning but never interrupts the main
        processing loop.  The heartbeat key's TTL (_HEARTBEAT_TTL) is longer
        than the write interval so transient Redis blips don't create false
        "worker dead" signals.
        """
        while self._running:
            try:
                client = await get_redis_client()
                record = json.dumps({
                    "status": "alive",
                    "updated_at": datetime.now(UTC).isoformat(),
                })
                await client.set(WORKER_HEARTBEAT_KEY, record, ex=_HEARTBEAT_TTL)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[Worker] Heartbeat write failed: %s", exc)
            await asyncio.sleep(_HEARTBEAT_INTERVAL)
