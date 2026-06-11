"""
Persistence service — orchestrates writing a complete review run to PostgreSQL.

Called by the worker after every job (completed or failed).  Designed to be:
  - Idempotent: re-running with the same delivery_id does not duplicate data.
  - Fault-tolerant: caller must wrap the call in try/except; failures should
    never affect the Redis-based review flow.
  - Self-contained: opens its own session so it can be called from the worker
    (which has no FastAPI request context).

Data sources:
  graph_state  — owner, repo, pr_number, head_sha, base_sha, installation_id,
                 status, started_at, completed_at, error
  webhook_payload (Redis) — PR title, author, branches, html_url, state,
                            github_repo_id, default_branch, event_action
  review_result — provider, model, findings, summary
  review_submission — event, commit_id, body, comments
"""
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.repository import Repository
from app.repositories.pull_request_repo import upsert_pull_request
from app.repositories.repository_repo import upsert_repository
from app.repositories.review_job_repo import (
    create_or_update_review_job,
    save_findings_idempotent,
    upsert_review_submission,
    upsert_review_summary,
)
from app.schemas.github_review import ReviewSubmission as ReviewSubmissionSchema
from app.schemas.review_result import ReviewResult as ReviewResultSchema
from app.services.redis_service import get_webhook_payload

logger = logging.getLogger(__name__)


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO-8601 string into a timezone-aware datetime, or return None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


async def _resolve_installation_id(
    raw: Any,
    full_name: str,
) -> int:
    """
    Return a valid GitHub installation ID.

    Priority:
      1. The value from graph_state if it's a positive integer.
      2. The value already stored in the DB for this repository.
      3. Raise ValueError — zero is not a valid GitHub installation ID.
    """
    if raw:
        try:
            parsed = int(raw)
            if parsed > 0:
                return parsed
        except (TypeError, ValueError):
            pass

    # Fallback: check the existing DB record
    async with AsyncSessionLocal() as session:
        row = await session.scalar(
            select(Repository.installation_id).where(Repository.full_name == full_name)
        )
        if row and row > 0:
            return int(row)

    raise ValueError(
        f"Cannot persist delivery for {full_name!r}: "
        f"installation_id is missing or zero in graph_state and no existing DB record found."
    )


async def persist_review_run(
    delivery_id: str,
    graph_state: dict,
    review_result: ReviewResultSchema | None,
    review_submission: ReviewSubmissionSchema | None,
    *,
    dry_run: bool = True,
    submitted_to_github: bool = False,
    github_review_id: int | None = None,
) -> dict[str, Any]:
    """
    Persist one complete review run to PostgreSQL.

    Parameters
    ----------
    delivery_id:
        GitHub webhook delivery ID — the unique job key.
    graph_state:
        The lightweight dict returned by ``get_graph_state(delivery_id)``.
        Required fields: owner, repo, pr_number.
    review_result:
        The completed ReviewResult (None for failed jobs).
    review_submission:
        The generated ReviewSubmission payload (None for failed jobs).
    dry_run:
        Whether this run was executed in dry-run mode (no GitHub API calls).
        Passed through from the worker's ``_submit_review()`` return value.
    submitted_to_github:
        Whether the review was actually posted to the GitHub API.
    github_review_id:
        The GitHub review object ID returned by the API, if submission succeeded.

    Returns
    -------
    dict
        Summary of what was persisted.

    Raises
    ------
    ValueError
        If required fields (owner, repo, pr_number) are missing from graph_state,
        or if installation_id cannot be resolved.
    Exception
        Any database error propagates to the caller for logging.
    """
    # ── Extract required fields ────────────────────────────────────────────────
    owner = graph_state.get("owner") or ""
    repo = graph_state.get("repo") or ""
    pr_number_raw = graph_state.get("pr_number")
    installation_id_raw = graph_state.get("installation_id")
    full_name = graph_state.get("repository") or f"{owner}/{repo}"
    status = graph_state.get("status", "failed")
    head_sha = graph_state.get("head_sha")
    base_sha = graph_state.get("base_sha")
    started_at = _parse_dt(graph_state.get("started_at"))
    completed_at = _parse_dt(graph_state.get("completed_at"))
    error_message = graph_state.get("error")

    if not owner or not repo or pr_number_raw is None:
        raise ValueError(
            f"Cannot persist delivery_id={delivery_id!r}: "
            f"graph_state is missing owner/repo/pr_number — got {graph_state}"
        )

    pr_number = int(pr_number_raw)
    installation_id = await _resolve_installation_id(installation_id_raw, full_name)

    # ── Enrich with webhook payload (best-effort) ──────────────────────────────
    webhook: dict = {}
    try:
        webhook = await get_webhook_payload(delivery_id) or {}
    except Exception as exc:
        logger.warning(
            "[Persist] Could not load webhook payload: delivery_id=%s error=%s",
            delivery_id, exc,
        )

    pr_payload: dict = webhook.get("pull_request", {})
    base_repo: dict = pr_payload.get("base", {}).get("repo", {})

    title = pr_payload.get("title")
    author = (pr_payload.get("user") or {}).get("login")
    head_branch = (pr_payload.get("head") or {}).get("ref")
    base_branch = (pr_payload.get("base") or {}).get("ref")
    html_url = pr_payload.get("html_url")
    pr_state = pr_payload.get("state")
    github_repo_id = base_repo.get("id")
    default_branch = base_repo.get("default_branch")
    event_action = webhook.get("action")

    # Use graph_state SHAs if webhook didn't have them
    if not head_sha:
        head_sha = (pr_payload.get("head") or {}).get("sha")
    if not base_sha:
        base_sha = (pr_payload.get("base") or {}).get("sha")

    # ── Derive duration ────────────────────────────────────────────────────────
    duration_ms: int | None = None
    if started_at and completed_at:
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)

    # ── Provider / model ───────────────────────────────────────────────────────
    provider = review_result.provider if review_result else None
    model = review_result.model if review_result else None

    # ── Database writes ────────────────────────────────────────────────────────
    findings_saved = 0
    async with AsyncSessionLocal() as session:
        async with session.begin():
            # 1. Upsert repository
            repository = await upsert_repository(
                session,
                owner=owner,
                name=repo,
                full_name=full_name,
                installation_id=installation_id,
                github_repo_id=github_repo_id,
                default_branch=default_branch,
            )

            # 2. Upsert pull request
            pull_request = await upsert_pull_request(
                session,
                repository_id=repository.id,
                pr_number=pr_number,
                title=title,
                author=author,
                base_branch=base_branch,
                head_branch=head_branch,
                base_sha=base_sha,
                head_sha=head_sha,
                html_url=html_url,
                state=pr_state,
            )

            # 3. Upsert review job
            review_job = await create_or_update_review_job(
                session,
                delivery_id=delivery_id,
                repository_id=repository.id,
                pull_request_id=pull_request.id,
                status=status,
                provider=provider,
                model=model,
                event_action=event_action,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                error_message=error_message,
            )

            # 4. Save findings (idempotent)
            if review_result and review_result.findings:
                finding_rows = [
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
                    for f in review_result.findings
                ]
                findings_saved = await save_findings_idempotent(
                    session, review_job.id, finding_rows
                )

            # 5. Upsert summary
            if review_result:
                s = review_result.summary
                await upsert_review_summary(
                    session,
                    review_job_id=review_job.id,
                    verdict=s.verdict,
                    risk_level=s.risk_level,
                    severity_score=s.severity_score,
                    summary_text=s.summary_text,
                    total_findings=s.total_findings,
                    critical_count=s.critical_count,
                    high_count=s.high_count,
                    medium_count=s.medium_count,
                    low_count=s.low_count,
                )

            # 6. Upsert submission payload
            if review_submission:
                comments_data = [
                    c.model_dump() for c in review_submission.comments
                ]
                await upsert_review_submission(
                    session,
                    review_job_id=review_job.id,
                    event=review_submission.event,
                    commit_id=review_submission.commit_id,
                    body=review_submission.body,
                    comments_json=comments_data,
                    dry_run=dry_run,
                    submitted_to_github=submitted_to_github,
                    github_review_id=github_review_id,
                )

    logger.info(
        "[Persist] Saved: delivery_id=%s repo=%s pr=%d status=%s "
        "findings=%d has_summary=%s has_submission=%s dry_run=%s submitted=%s",
        delivery_id, full_name, pr_number, status,
        findings_saved,
        review_result is not None,
        review_submission is not None,
        dry_run,
        submitted_to_github,
    )

    return {
        "delivery_id": delivery_id,
        "repository": full_name,
        "pr_number": pr_number,
        "status": status,
        "findings_saved": findings_saved,
        "persisted": True,
    }
