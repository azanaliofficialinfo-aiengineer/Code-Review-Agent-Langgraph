"""
Persistent store for ReviewSubmission payloads.

Payloads are stored in Redis with a 48-hour TTL and used for:
  - Dry-run inspection (the payload that *would* have been sent to GitHub)
  - Post-submission audit (the payload that *was* sent to GitHub)
  - The GET /reviews/{delivery_id}/submission and
    GET /debug/review-submission/{delivery_id} endpoints
"""
from app.core.constants import REVIEW_SUBMISSION_KEY_PREFIX
from app.schemas.github_review import ReviewSubmission
from app.services.redis_service import get_redis_client

_TTL = 48 * 60 * 60  # 48 hours


def _key(delivery_id: str) -> str:
    return f"{REVIEW_SUBMISSION_KEY_PREFIX}{delivery_id}"


async def save_review_submission(delivery_id: str, submission: ReviewSubmission) -> None:
    """Serialize and store the ReviewSubmission in Redis."""
    client = await get_redis_client()
    await client.set(_key(delivery_id), submission.model_dump_json(), ex=_TTL)


async def get_review_submission(delivery_id: str) -> ReviewSubmission | None:
    """Return the stored ReviewSubmission, or None if absent / expired."""
    client = await get_redis_client()
    raw = await client.get(_key(delivery_id))
    if raw is None:
        return None
    return ReviewSubmission.model_validate_json(raw)
