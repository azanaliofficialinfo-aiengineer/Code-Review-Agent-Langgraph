"""
Duplicate review prevention.

Before submitting a GitHub review, the worker checks whether a review for the
same delivery ID has already been posted.  This prevents double-posting when
GitHub redelivers a webhook (e.g. after a temporary worker outage).

Redis key: github:review_lock:{delivery_id}  (TTL 24 h)

The lock is set *after* a successful submission (dry-run store or live GitHub
call) so that a failed submission is always retryable.
"""
from app.core.constants import REVIEW_LOCK_KEY_PREFIX
from app.services.redis_service import get_redis_client

_LOCK_TTL = 24 * 60 * 60  # 24 hours


def _lock_key(delivery_id: str) -> str:
    return f"{REVIEW_LOCK_KEY_PREFIX}{delivery_id}"


async def is_already_reviewed(delivery_id: str) -> bool:
    """Return True if a review has already been submitted for this delivery."""
    client = await get_redis_client()
    return await client.exists(_lock_key(delivery_id)) > 0


async def mark_as_reviewed(delivery_id: str) -> None:
    """
    Record that the review for this delivery has been submitted.

    Call this only *after* the submission has been persisted (dry-run or live)
    so that failures remain retryable.
    """
    client = await get_redis_client()
    await client.set(_lock_key(delivery_id), "1", ex=_LOCK_TTL)
