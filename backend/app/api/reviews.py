"""
Public review status and result endpoints.

GET /reviews/worker/status              — worker liveness (no auth required)
GET /reviews                            — paginated review list (DB-backed)
GET /reviews/{delivery_id}/status       — review pipeline status poll
GET /reviews/{delivery_id}/result       — full ReviewResult (only when completed)
GET /reviews/{delivery_id}/submission   — stored GitHub review payload
GET /reviews/{delivery_id}              — full persisted detail (DB-backed)

Route order is significant: /worker/status must appear before /{delivery_id}/status
so that the literal segment "worker" is matched first, not consumed as a delivery_id.
"""
import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_auth
from app.core.constants import WORKER_HEARTBEAT_KEY
from app.db.session import get_db
from app.repositories.review_job_repo import (
    count_reviews as _count_reviews,
    get_review_detail as _get_review_detail,
    get_review_job_by_delivery_id as _get_job,
    list_reviews as _list_reviews,
)
from app.schemas.db_schemas import (
    FindingInfo,
    PaginatedFindingList,
    PaginatedReviews,
    PullRequestInfo,
    RepositoryInfo,
    ReviewDetail,
    ReviewListItem,
    SubmissionInfo,
    SummaryInfo,
)
from app.services.graph_state_store import get_graph_state
from app.services.redis_service import get_redis_client
from app.services.review_result_store import get_review_result
from app.services.review_submission_store import get_review_submission

logger = logging.getLogger(__name__)

_VALID_STATUSES = frozenset({"queued", "fetching_context", "reviewing", "completed", "failed"})

router = APIRouter(prefix="/reviews", tags=["reviews"])


# ── GET /reviews/worker/status ────────────────────────────────────────────────
# No auth — monitoring systems need this without credentials.
# Must be declared FIRST to prevent "worker" being captured as {delivery_id}.

@router.get(
    "/worker/status",
    summary="Get the liveness status of the review worker process",
)
async def get_worker_status() -> dict:
    """
    Returns liveness information sourced from the worker heartbeat key.

    The worker writes to `github:worker:heartbeat` every 10 seconds with a
    30-second TTL.  If the key is absent the worker has been dead for > 30 s.
    """
    client = await get_redis_client()
    raw = await client.get(WORKER_HEARTBEAT_KEY)

    if raw is None:
        return {
            "status": "dead",
            "updated_at": None,
            "last_heartbeat_ago_seconds": None,
        }

    try:
        record: dict[str, Any] = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"status": "unknown", "updated_at": None, "last_heartbeat_ago_seconds": None}

    updated_at = record.get("updated_at")
    ago: float | None = None
    if updated_at:
        try:
            dt = datetime.fromisoformat(updated_at)
            ago = round((datetime.now(UTC) - dt).total_seconds(), 1)
        except (ValueError, TypeError):
            pass

    return {
        "status": record.get("status", "unknown"),
        "updated_at": updated_at,
        "last_heartbeat_ago_seconds": ago,
    }


# ── GET /reviews ──────────────────────────────────────────────────────────────

@router.get(
    "",
    summary="List review jobs (DB-backed)",
    response_model=PaginatedReviews,
    dependencies=[Depends(require_api_auth)],
)
async def list_reviews_endpoint(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None, description="Filter by job status"),
    repository: str | None = Query(
        None, description="Filter by repository full_name (owner/repo)"
    ),
    session: AsyncSession = Depends(get_db),
) -> PaginatedReviews:
    """
    Return a paginated list of review jobs from PostgreSQL, newest first.

    All parameters are optional.  Use `repository=owner/repo` to narrow to
    a single repository.
    """
    if status is not None and status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid status filter '{status}'. "
                f"Valid values: {sorted(_VALID_STATUSES)}"
            ),
        )

    rows, total = await _list_reviews(
        session,
        limit=limit,
        offset=offset,
        status=status,
        repository_full_name=repository,
    ), await _count_reviews(session, status=status, repository_full_name=repository)

    return PaginatedReviews(
        items=[ReviewListItem(**row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ── GET /reviews/{delivery_id}/status ─────────────────────────────────────────

@router.get(
    "/{delivery_id}/status",
    summary="Get the current status of a review pipeline run",
    dependencies=[Depends(require_api_auth)],
)
async def get_review_status(
    delivery_id: str,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns the lightweight status summary for the given delivery ID.

    Checks Redis first (live state); falls back to PostgreSQL when the
    48-hour Redis TTL has expired.  A `source` field indicates which
    backend answered the request.

    The `status` field progresses through:
      queued → fetching_context → reviewing → completed
    or terminates at `failed` with an `error` description.
    """
    state = await get_graph_state(delivery_id)
    if state is not None:
        return state

    # Redis miss — try the database
    job = await _get_job(session, delivery_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No review found for delivery_id '{delivery_id}'. "
                "The delivery may not have been received or may have expired."
            ),
        )
    return {
        "delivery_id": delivery_id,
        "status": job.status,
        "error": job.error_message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "source": "database",
    }


# ── GET /reviews/{delivery_id}/result ─────────────────────────────────────────

@router.get(
    "/{delivery_id}/result",
    summary="Get the full ReviewResult for a completed review",
    dependencies=[Depends(require_api_auth)],
)
async def get_review_result_endpoint(
    delivery_id: str,
    session: AsyncSession = Depends(get_db),
) -> Any:
    """
    Returns the complete `ReviewResult` (findings, summary, file lists).

    Checks Redis first; falls back to PostgreSQL when the 48-hour TTL expires.

    HTTP semantics:
      404  — delivery ID unknown in both Redis and PostgreSQL
      202  — review is in progress
      422  — review pipeline failed
      200  — review completed; body is the full ReviewResult
    """
    state = await get_graph_state(delivery_id)

    if state is None:
        # Redis miss — check DB for status
        job = await _get_job(session, delivery_id)
        if job is None:
            raise HTTPException(
                status_code=404,
                detail=f"No review found for delivery_id '{delivery_id}'.",
            )
        if job.status == "failed":
            raise HTTPException(
                status_code=422,
                detail={
                    "delivery_id": delivery_id,
                    "status": "failed",
                    "error": job.error_message,
                    "message": "Review pipeline failed. See 'error' for details.",
                },
            )
        if job.status != "completed":
            return JSONResponse(
                status_code=202,
                content={
                    "delivery_id": delivery_id,
                    "status": job.status,
                    "message": f"Review is not yet complete (status: {job.status}).",
                    "source": "database",
                },
            )
        # Completed but Redis TTL expired — reconstruct from DB
        detail = await _get_review_detail(session, delivery_id, findings_limit=None)
        if detail is None:
            raise HTTPException(
                status_code=404,
                detail="Review result data not found.",
            )
        return _build_result_from_detail(detail)

    status = state.get("status")

    if status in ("queued", "fetching_context", "reviewing"):
        return JSONResponse(
            status_code=202,
            content={
                "delivery_id": delivery_id,
                "status": status,
                "message": (
                    f"Review is not yet complete (status: {status}). "
                    f"Poll GET /reviews/{delivery_id}/status and retry when "
                    "status == 'completed'."
                ),
            },
        )

    if status == "failed":
        raise HTTPException(
            status_code=422,
            detail={
                "delivery_id": delivery_id,
                "status": "failed",
                "error": state.get("error"),
                "message": "Review pipeline failed. See 'error' for details.",
            },
        )

    if status == "completed":
        result = await get_review_result(delivery_id)
        if result is not None:
            return result.model_dump()
        # Result evicted from Redis before state — fall back to DB
        detail = await _get_review_detail(session, delivery_id, findings_limit=None)
        if detail is None:
            raise HTTPException(
                status_code=404,
                detail="Review result data not found. It may have expired.",
            )
        return _build_result_from_detail(detail)

    raise HTTPException(
        status_code=500,
        detail=f"Unexpected review status '{status}' for delivery_id '{delivery_id}'.",
    )


def _build_result_from_detail(detail: dict) -> dict:
    """Reconstruct a ReviewResult-shaped dict from a DB detail dict."""
    summary = detail["summary"]
    findings = detail["findings"]
    return {
        "source": "database",
        "summary": {
            "verdict": summary.verdict,
            "risk_level": summary.risk_level,
            "severity_score": summary.severity_score,
            "summary_text": summary.summary_text,
            "total_findings": summary.total_findings,
            "critical_count": summary.critical_count,
            "high_count": summary.high_count,
            "medium_count": summary.medium_count,
            "low_count": summary.low_count,
        } if summary else None,
        "findings": [
            {
                "file_path": f.file_path,
                "line": f.line,
                "severity": f.severity,
                "category": f.category,
                "title": f.title,
                "description": f.description,
                "suggestion": f.suggestion,
                "confidence": f.confidence,
                "should_comment": f.should_comment,
            }
            for f in findings
        ],
    }


# ── GET /reviews/{delivery_id}/submission ─────────────────────────────────────

@router.get(
    "/{delivery_id}/submission",
    summary="Get the stored GitHub review payload for a completed review",
    dependencies=[Depends(require_api_auth)],
)
async def get_review_submission_endpoint(delivery_id: str) -> Any:
    """
    Return the ReviewSubmission payload stored after the review worker ran.

    In dry-run mode (default) this is the payload that *would* have been sent
    to GitHub.  In live mode it is the payload that *was* sent.

    HTTP semantics:
      404 — no submission found (review not yet complete, or payload expired)
      200 — the ReviewSubmission as JSON
    """
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


# ── GET /reviews/{delivery_id} ────────────────────────────────────────────────
# Must be the LAST route so the bare /{delivery_id} param doesn't shadow the
# more-specific sub-path routes above.

@router.get(
    "/{delivery_id}",
    summary="Get full review detail (DB-backed)",
    response_model=ReviewDetail,
    dependencies=[Depends(require_api_auth)],
)
async def get_review_detail_endpoint(
    delivery_id: str,
    findings_limit: int = Query(50, ge=1, le=200, description="Max findings to return"),
    findings_offset: int = Query(0, ge=0, description="Findings pagination offset"),
    session: AsyncSession = Depends(get_db),
) -> ReviewDetail:
    """
    Return the full persisted review detail for a delivery ID from PostgreSQL.

    For transient Redis-based status polling use GET /{delivery_id}/status.
    Use `findings_limit` and `findings_offset` to paginate through findings.

    HTTP semantics:
      404 — delivery ID not found in the database
      200 — full ReviewDetail including paginated findings and submission payload
    """
    detail = await _get_review_detail(
        session,
        delivery_id,
        findings_limit=findings_limit,
        findings_offset=findings_offset,
    )
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail=f"No persisted review found for delivery_id '{delivery_id}'.",
        )

    job = detail["job"]
    repo = detail["repository"]
    pr = detail["pull_request"]
    summary = detail["summary"]
    raw_findings = detail["findings"]
    findings_total = detail["findings_total"]
    submission = detail["submission"]

    return ReviewDetail(
        delivery_id=job.delivery_id,
        status=job.status,
        provider=job.provider,
        model=job.model,
        event_action=job.event_action,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_ms=job.duration_ms,
        error_message=job.error_message,
        created_at=job.created_at,
        repository=RepositoryInfo(
            owner=repo.owner,
            name=repo.name,
            full_name=repo.full_name,
            installation_id=repo.installation_id,
            default_branch=repo.default_branch,
            is_active=repo.is_active,
        ),
        pull_request=PullRequestInfo(
            pr_number=pr.pr_number,
            title=pr.title,
            author=pr.author,
            base_branch=pr.base_branch,
            head_branch=pr.head_branch,
            base_sha=pr.base_sha,
            head_sha=pr.head_sha,
            html_url=pr.html_url,
            state=pr.state,
        ),
        summary=SummaryInfo(
            verdict=summary.verdict,
            risk_level=summary.risk_level,
            severity_score=summary.severity_score,
            summary_text=summary.summary_text,
            total_findings=summary.total_findings,
            critical_count=summary.critical_count,
            high_count=summary.high_count,
            medium_count=summary.medium_count,
            low_count=summary.low_count,
        ) if summary else None,
        findings=PaginatedFindingList(
            items=[
                FindingInfo(
                    file_path=f.file_path,
                    line=f.line,
                    severity=f.severity,
                    category=f.category,
                    title=f.title,
                    description=f.description,
                    suggestion=f.suggestion,
                    confidence=f.confidence,
                    should_comment=f.should_comment,
                )
                for f in raw_findings
            ],
            total=findings_total,
            limit=findings_limit,
            offset=findings_offset,
        ),
        submission=SubmissionInfo(
            event=submission.event,
            commit_id=submission.commit_id,
            dry_run=submission.dry_run,
            submitted_to_github=submission.submitted_to_github,
            inline_comment_count=(
                len(submission.comments_json) if submission.comments_json else 0
            ),
            github_review_id=submission.github_review_id,
            created_at=submission.created_at,
        ) if submission else None,
    )
