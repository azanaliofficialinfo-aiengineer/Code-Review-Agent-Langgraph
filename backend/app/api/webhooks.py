import json
import logging
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import settings
from app.core.security import verify_github_signature
from app.services.redis_service import enqueue_review_job, store_webhook_payload

logger = logging.getLogger(__name__)

router = APIRouter()

# The only PR actions we act on; everything else is acknowledged and dropped.
_ACTIONABLE_PR_ACTIONS = frozenset({"opened", "synchronize", "reopened"})


@router.post("/webhooks/github", summary="Receive GitHub webhook events")
async def github_webhook(
    request: Request,
    x_github_event: Annotated[str | None, Header()] = None,
    x_github_delivery: Annotated[str | None, Header()] = None,
    x_hub_signature_256: Annotated[str | None, Header()] = None,
) -> dict:
    """
    Entry point for all GitHub App webhook deliveries.

    Processing order
    ----------------
    1. Read raw body (must happen before any parsing to preserve bytes for HMAC).
    2. Verify HMAC-SHA256 signature — reject 401 on failure.
    3. Validate required headers.
    4. Gate on event type — only `pull_request` is handled.
    5. Parse JSON payload.
    6. Dispatch on action; ignore unsupported actions with 200.
    7. Store accepted payload in Redis.
    """
    # ── 1. Raw body ────────────────────────────────────────────────────────
    body: bytes = await request.body()

    # ── 2. Signature verification ──────────────────────────────────────────
    if not verify_github_signature(body, x_hub_signature_256 or "", settings.GITHUB_WEBHOOK_SECRET):
        logger.warning(
            "Webhook signature verification failed",
            extra={"delivery_id": x_github_delivery, "event": x_github_event},
        )
        raise HTTPException(status_code=401, detail="Invalid or missing webhook signature")

    # ── 3. Required headers ────────────────────────────────────────────────
    if not x_github_event:
        raise HTTPException(status_code=400, detail="Missing X-GitHub-Event header")

    if not x_github_delivery:
        raise HTTPException(status_code=400, detail="Missing X-GitHub-Delivery header")

    # ── 4. Event type gate ─────────────────────────────────────────────────
    if x_github_event != "pull_request":
        logger.debug("Ignoring unsupported event type: %s", x_github_event)
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported event: '{x_github_event}'. Only 'pull_request' events are processed.",
        )

    # ── 5. Parse payload ───────────────────────────────────────────────────
    try:
        payload: dict = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Request body is not valid JSON")

    action: str = payload.get("action", "")

    # ── 6. Action gate ─────────────────────────────────────────────────────
    if action not in _ACTIONABLE_PR_ACTIONS:
        logger.debug("Ignoring pull_request action: %s", action)
        return {
            "status": "ignored",
            "reason": "unsupported_pull_request_action",
            "action": action,
        }

    # ── 7. Store and respond ───────────────────────────────────────────────
    repository: str = payload.get("repository", {}).get("full_name", "unknown/unknown")
    pr_number: int | None = payload.get("pull_request", {}).get("number")

    await store_webhook_payload(
        delivery_id=x_github_delivery,
        event_type=x_github_event,
        payload=payload,
    )

    await enqueue_review_job(x_github_delivery)

    logger.info(
        "Accepted and queued pull_request webhook",
        extra={
            "delivery_id": x_github_delivery,
            "action": action,
            "repository": repository,
            "pr_number": pr_number,
        },
    )

    return {
        "status": "accepted",
        "event": x_github_event,
        "action": action,
        "delivery_id": x_github_delivery,
        "repository": repository,
        "pull_request": pr_number,
        "queued": True,
    }
