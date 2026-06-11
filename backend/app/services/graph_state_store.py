"""
Redis persistence for LangGraph execution state.

Stores a lightweight metadata summary plus the GitHub fields required for
Phase 6 comment posting (installation_id, head_sha, etc.).  The full
pr_context and review_result blobs are NOT stored here — they would be too
large and are available separately in review_result_store.py.

Key format : github:graph_state:{delivery_id}
TTL        : 48 hours
"""
import json
import logging
from datetime import UTC, datetime

from app.services.redis_service import get_redis_client

logger = logging.getLogger(__name__)

_KEY_PREFIX = "github:graph_state"
_TTL = 48 * 3600  # 48 hours in seconds


def _state_key(delivery_id: str) -> str:
    return f"{_KEY_PREFIX}:{delivery_id}"


async def save_graph_state(delivery_id: str, state: dict) -> None:
    """
    Persist a summary of the graph state to Redis.

    Extracts all metadata needed by both the /reviews endpoints AND Phase 6
    comment posting.  The caller must pass the full in-memory ReviewState
    dict (or a compatible superset) so that pr_context metadata is available
    when it has been fetched.

    Phase 6 required fields preserved here:
        installation_id, owner, repo, head_sha, base_sha
    """
    client = await get_redis_client()

    pr_context = state.get("pr_context") or {}
    pr_meta = pr_context.get("metadata", {})

    review_result = state.get("review_result") or {}
    review_summary = review_result.get("summary")

    record = {
        "delivery_id": delivery_id,
        "status": state.get("status"),
        "started_at": state.get("started_at"),
        "completed_at": state.get("completed_at"),
        "error": state.get("error"),
        # ── Identifiers ───────────────────────────────────────────────────
        "repository": pr_meta.get("repository_full_name"),
        "pr_number": pr_meta.get("pr_number"),
        # ── Phase 6 required metadata ─────────────────────────────────────
        "installation_id": pr_meta.get("installation_id"),
        "owner": pr_meta.get("owner"),
        "repo": pr_meta.get("repo"),
        "head_sha": pr_meta.get("head_sha"),
        "base_sha": pr_meta.get("base_sha"),
        # ── Review summary (convenience) ──────────────────────────────────
        "summary": review_summary,
    }

    await client.set(_state_key(delivery_id), json.dumps(record), ex=_TTL)
    logger.debug(
        "Saved graph state: delivery_id=%s status=%s",
        delivery_id,
        record["status"],
    )


async def get_graph_state(delivery_id: str) -> dict | None:
    """
    Retrieve the stored graph state summary.

    Returns None when the key is absent or has expired.
    """
    client = await get_redis_client()
    raw = await client.get(_state_key(delivery_id))
    if raw is None:
        return None
    return json.loads(raw)


async def mark_graph_state_failed(delivery_id: str, error: str) -> None:
    """
    Atomically update an existing graph state record to status=failed.

    Reads the current stored record (preserving already-saved metadata such
    as installation_id, repository, etc.) and writes it back with the failure
    details.  Safe to call even if no record exists yet — creates a minimal
    failed record in that case.

    Used by the worker to record job timeouts without going through the graph.
    """
    client = await get_redis_client()
    key = _state_key(delivery_id)

    raw = await client.get(key)
    record: dict = json.loads(raw) if raw else {"delivery_id": delivery_id}

    record.update({
        "status": "failed",
        "error": error,
        "completed_at": datetime.now(UTC).isoformat(),
    })

    await client.set(key, json.dumps(record), ex=_TTL)
    logger.info(
        "Marked graph state failed: delivery_id=%s error=%s",
        delivery_id,
        error,
    )
