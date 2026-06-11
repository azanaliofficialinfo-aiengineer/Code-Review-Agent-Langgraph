"""
Development-only debug endpoints.

Registered in main.py only when ENVIRONMENT != "production".
All routes return 404 in production, preventing accidental exposure.
"""
import logging
import time

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_api_auth
from app.core.config import settings
from app.core.exceptions import (
    AIProviderConfigError,
    AIReviewError,
    DeliveryNotFoundError,
    GitHubAPIError,
    GitHubAuthError,
    MissingInstallationError,
)
from app.schemas.pr_context import PRContext
from app.schemas.review_result import ReviewResult
from app.services.graph_state_store import get_graph_state
from app.services.pr_fetcher import build_pr_context_from_delivery
from app.services.review_submission_store import get_review_submission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug", tags=["debug"], dependencies=[Depends(require_api_auth)])


def _guard_production() -> None:
    """Raise 404 immediately if running in production."""
    if settings.ENVIRONMENT == "production":
        raise HTTPException(status_code=404, detail="Not found")


# ── /debug/pr-context ─────────────────────────────────────────────────────────

@router.get(
    "/pr-context/{delivery_id}",
    response_model=PRContext,
    summary="[DEV] Fetch PR context for a webhook delivery",
)
async def get_pr_context(delivery_id: str) -> PRContext:
    """
    Trigger a full PR context build for an already-stored webhook delivery.
    Disabled in production (returns 404).
    """
    _guard_production()
    logger.info("Debug: building PR context for delivery_id=%s", delivery_id)

    try:
        return await build_pr_context_from_delivery(delivery_id)
    except DeliveryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MissingInstallationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GitHubAuthError as exc:
        raise HTTPException(status_code=503, detail=f"GitHub App authentication failed: {exc}") from exc
    except GitHubAPIError as exc:
        raise HTTPException(status_code=502, detail=f"GitHub API error {exc.status_code}: {exc.message}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ── /debug/review-result ──────────────────────────────────────────────────────

@router.get(
    "/review-result/{delivery_id}",
    summary="[DEV] Run AI review for a webhook delivery",
)
async def get_review_result(delivery_id: str) -> dict:
    """
    Build a PRContext then run the full AI review pipeline and return the result.

    Response includes a `_debug.elapsed_seconds` field for timing diagnostics.
    Disabled in production (returns 404).
    """
    _guard_production()
    logger.info("Debug: running AI review for delivery_id=%s", delivery_id)

    t0 = time.perf_counter()

    # ── Fetch PR context ───────────────────────────────────────────────────
    try:
        pr_context = await build_pr_context_from_delivery(delivery_id)
    except DeliveryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MissingInstallationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GitHubAuthError as exc:
        raise HTTPException(status_code=503, detail=f"GitHub App auth failed: {exc}") from exc
    except GitHubAPIError as exc:
        raise HTTPException(status_code=502, detail=f"GitHub API error {exc.status_code}: {exc.message}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # ── Run AI review ──────────────────────────────────────────────────────
    try:
        from app.services.ai_provider import get_ai_provider  # noqa: PLC0415
        provider = get_ai_provider()
        result: ReviewResult = await provider.review_pr(pr_context)
    except AIProviderConfigError as exc:
        raise HTTPException(status_code=503, detail=f"AI provider misconfigured: {exc}") from exc
    except AIReviewError as exc:
        raise HTTPException(status_code=502, detail=f"AI review failed: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error during AI review for delivery_id=%s", delivery_id)
        raise HTTPException(status_code=500, detail=f"Unexpected review error: {type(exc).__name__}") from exc

    elapsed = round(time.perf_counter() - t0, 2)

    return {
        **result.model_dump(),
        "_debug": {
            "elapsed_seconds": elapsed,
            "reviewed_file_count": len(result.reviewed_files),
            "skipped_file_count": len(result.skipped_files),
        },
    }


# ── /debug/graph-state ────────────────────────────────────────────────────────

@router.get(
    "/graph-state/{delivery_id}",
    summary="[DEV] Inspect LangGraph execution state for a delivery",
)
async def get_graph_state_debug(delivery_id: str) -> dict:
    """
    Return the stored LangGraph execution state summary for the given delivery ID.

    Useful for debugging pipeline failures — shows status, timestamps,
    repository info, and the final review summary (if completed).
    Disabled in production (returns 404).
    """
    _guard_production()
    logger.info("Debug: fetching graph state for delivery_id=%s", delivery_id)

    state = await get_graph_state(delivery_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"No graph state found for delivery_id '{delivery_id}'. "
                   "The review may not have started yet or may have expired.",
        )
    return state


# ── /debug/review-submission ──────────────────────────────────────────────────

@router.get(
    "/review-submission/{delivery_id}",
    summary="[DEV] Inspect the generated GitHub review payload for a delivery",
)
async def get_review_submission_debug(delivery_id: str) -> dict:
    """
    Return the ReviewSubmission payload stored after a completed review.

    In dry-run mode (default) this is the payload that *would* have been sent
    to GitHub.  In live mode it is the payload that *was* sent.

    Disabled in production (returns 404).
    """
    _guard_production()
    logger.info("Debug: fetching review submission for delivery_id=%s", delivery_id)

    submission = await get_review_submission(delivery_id)
    if submission is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No review submission found for delivery_id '{delivery_id}'. "
                "The review may not have completed yet, or the payload has expired (48 h TTL)."
            ),
        )
    return submission.model_dump()
