import json
import logging
from datetime import UTC, datetime

from redis.asyncio import Redis

from app.core.config import settings
from app.core.constants import REVIEW_QUEUE_KEY

logger = logging.getLogger(__name__)

_client: Redis | None = None

# 24 hours in seconds
_WEBHOOK_TTL = 86_400
_WEBHOOK_KEY_PREFIX = "github:webhook"


async def get_redis_client() -> Redis:
    """Return the module-level Redis client, initialising it on first call."""
    global _client
    if _client is None:
        _client = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return _client


async def close_redis_client() -> None:
    """Gracefully close the connection pool (called from lifespan shutdown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.info("Redis client closed")


async def ping_redis() -> bool:
    """Return True if Redis is reachable, False otherwise."""
    try:
        client = await get_redis_client()
        return await client.ping()
    except Exception:
        return False


async def store_webhook_payload(
    delivery_id: str,
    event_type: str,
    payload: dict,
) -> None:
    """
    Persist a received GitHub webhook payload in Redis.

    Key format : github:webhook:{delivery_id}
    TTL        : 24 hours
    """
    client = await get_redis_client()
    key = f"{_WEBHOOK_KEY_PREFIX}:{delivery_id}"

    record = {
        "delivery_id": delivery_id,
        "event_type": event_type,
        "action": payload.get("action", ""),
        "repository": payload.get("repository", {}).get("full_name", ""),
        "pull_request_number": payload.get("pull_request", {}).get("number"),
        "received_at": datetime.now(UTC).isoformat(),
        "raw_payload": payload,
    }

    await client.set(key, json.dumps(record), ex=_WEBHOOK_TTL)
    logger.info(
        "Stored webhook payload",
        extra={
            "delivery_id": delivery_id,
            "event_type": event_type,
            "action": record["action"],
            "repository": record["repository"],
        },
    )


async def get_webhook_payload(delivery_id: str) -> dict | None:
    """
    Retrieve a previously stored webhook record from Redis.

    Returns the full record dict (including raw_payload), or None if the key
    has expired or was never stored.
    """
    client = await get_redis_client()
    key = f"{_WEBHOOK_KEY_PREFIX}:{delivery_id}"
    raw = await client.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def enqueue_review_job(delivery_id: str) -> None:
    """
    Push a delivery ID onto the review queue for async processing.

    Key  : github:review_queue  (Redis list, FIFO — rpush / lpop)
    Phase: jobs are consumed by the LangGraph worker starting in Phase 5.
    """
    client = await get_redis_client()
    await client.rpush(REVIEW_QUEUE_KEY, delivery_id)
    logger.info("Enqueued review job: delivery_id=%s", delivery_id)


async def dequeue_review_job() -> str | None:
    """
    Non-blocking pop of the next delivery ID from the review queue.

    Returns None when the queue is empty.
    A blocking worker (Phase 5) will use blpop instead; this helper is
    provided for polling-style consumers and tests.
    """
    client = await get_redis_client()
    result = await client.lpop(REVIEW_QUEUE_KEY)
    return result  # str | None (decode_responses=True)
