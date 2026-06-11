"""
Redis persistence for completed ReviewResult objects.

Stores the full serialised ReviewResult so that the /reviews/{delivery_id}/result
endpoint can return the complete findings list without hitting GitHub or the AI
provider again.

Key format : github:review_result:{delivery_id}
TTL        : 48 hours
"""
import logging

from app.schemas.review_result import ReviewResult
from app.services.redis_service import get_redis_client

logger = logging.getLogger(__name__)

_KEY_PREFIX = "github:review_result"
_TTL = 48 * 3600  # 48 hours in seconds


def _result_key(delivery_id: str) -> str:
    return f"{_KEY_PREFIX}:{delivery_id}"


async def save_review_result(delivery_id: str, result: ReviewResult) -> None:
    """Serialise and store a ReviewResult in Redis."""
    client = await get_redis_client()
    await client.set(_result_key(delivery_id), result.model_dump_json(), ex=_TTL)
    logger.info(
        "Saved review result: delivery_id=%s findings=%d verdict=%s",
        delivery_id,
        len(result.findings),
        result.summary.verdict,
    )


async def get_review_result(delivery_id: str) -> ReviewResult | None:
    """
    Retrieve and deserialise a stored ReviewResult.

    Returns None when the key is absent or has expired.
    """
    client = await get_redis_client()
    raw = await client.get(_result_key(delivery_id))
    if raw is None:
        return None
    return ReviewResult.model_validate_json(raw)
