"""
ReviewJob and child-table CRUD.

Covers: review_jobs, review_findings, review_summaries, review_submissions.
All writes are idempotent — re-running the same delivery_id is safe.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review_finding import ReviewFinding
from app.models.review_job import ReviewJob
from app.models.review_submission import ReviewSubmission
from app.models.review_summary import ReviewSummary

# ── ReviewJob ──────────────────────────────────────────────────────────────────


async def create_or_update_review_job(
    session: AsyncSession,
    delivery_id: str,
    repository_id: uuid.UUID,
    pull_request_id: uuid.UUID,
    status: str,
    provider: str | None = None,
    model: str | None = None,
    event_action: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    duration_ms: int | None = None,
    error_message: str | None = None,
) -> ReviewJob:
    """Upsert the review job keyed on delivery_id."""
    now = datetime.now(timezone.utc)
    stmt = (
        pg_insert(ReviewJob)
        .values(
            delivery_id=delivery_id,
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            status=status,
            provider=provider,
            model=model,
            event_action=event_action,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            error_message=error_message,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["delivery_id"],
            set_={
                "status": status,
                "provider": provider,
                "model": model,
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "error_message": error_message,
                "updated_at": now,
            },
        )
    )
    await session.execute(stmt)
    await session.flush()

    result = await session.execute(
        select(ReviewJob).where(ReviewJob.delivery_id == delivery_id)
    )
    return result.scalar_one()


async def get_review_job_by_delivery_id(
    session: AsyncSession,
    delivery_id: str,
) -> ReviewJob | None:
    result = await session.execute(
        select(ReviewJob).where(ReviewJob.delivery_id == delivery_id)
    )
    return result.scalar_one_or_none()


# ── ReviewFinding ──────────────────────────────────────────────────────────────


async def save_findings_idempotent(
    session: AsyncSession,
    review_job_id: uuid.UUID,
    findings: list[dict],
) -> int:
    """
    Bulk-insert findings for a job.  Idempotent: skipped if rows already exist.
    Returns the number of rows inserted (0 on repeat calls).
    """
    if not findings:
        return 0

    count = await session.scalar(
        select(func.count(ReviewFinding.id)).where(
            ReviewFinding.review_job_id == review_job_id
        )
    )
    if count and count > 0:
        return 0

    rows = [{"id": uuid.uuid4(), "review_job_id": review_job_id, **f} for f in findings]
    await session.execute(insert(ReviewFinding), rows)
    return len(rows)


# ── ReviewSummary ──────────────────────────────────────────────────────────────


async def upsert_review_summary(
    session: AsyncSession,
    review_job_id: uuid.UUID,
    verdict: str,
    risk_level: str,
    severity_score: int,
    summary_text: str,
    total_findings: int,
    critical_count: int,
    high_count: int,
    medium_count: int,
    low_count: int,
) -> None:
    stmt = (
        pg_insert(ReviewSummary)
        .values(
            review_job_id=review_job_id,
            verdict=verdict,
            risk_level=risk_level,
            severity_score=severity_score,
            summary_text=summary_text,
            total_findings=total_findings,
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
        )
        .on_conflict_do_update(
            constraint="uq_review_summaries_review_job_id",
            set_={
                "verdict": verdict,
                "risk_level": risk_level,
                "severity_score": severity_score,
                "summary_text": summary_text,
                "total_findings": total_findings,
                "critical_count": critical_count,
                "high_count": high_count,
                "medium_count": medium_count,
                "low_count": low_count,
            },
        )
    )
    await session.execute(stmt)


# ── ReviewSubmission ───────────────────────────────────────────────────────────


async def upsert_review_submission(
    session: AsyncSession,
    review_job_id: uuid.UUID,
    event: str,
    commit_id: str,
    body: str,
    comments_json: Any,
    dry_run: bool,
    submitted_to_github: bool = False,
    github_review_id: int | None = None,
) -> None:
    stmt = (
        pg_insert(ReviewSubmission)
        .values(
            review_job_id=review_job_id,
            event=event,
            commit_id=commit_id,
            body=body,
            comments_json=comments_json,
            dry_run=dry_run,
            submitted_to_github=submitted_to_github,
            github_review_id=github_review_id,
        )
        .on_conflict_do_update(
            constraint="uq_review_submissions_review_job_id",
            set_={
                "event": event,
                "commit_id": commit_id,
                "body": body,
                "comments_json": comments_json,
                "dry_run": dry_run,
                "submitted_to_github": submitted_to_github,
                "github_review_id": github_review_id,
            },
        )
    )
    await session.execute(stmt)


# ── Count helpers (for pagination totals) ─────────────────────────────────────


async def count_reviews(
    session: AsyncSession,
    status: str | None = None,
    repository_full_name: str | None = None,
) -> int:
    """Return total matching review_jobs for pagination metadata."""
    q = select(func.count(ReviewJob.id))
    if repository_full_name:
        q = q.join(Repository, ReviewJob.repository_id == Repository.id)
        q = q.where(Repository.full_name == repository_full_name)
    if status:
        q = q.where(ReviewJob.status == status)
    return await session.scalar(q) or 0


async def count_repository_reviews(
    session: AsyncSession,
    full_name: str,
) -> int:
    """Return total review_jobs for one repository."""
    repo_id_subq = (
        select(Repository.id)
        .where(Repository.full_name == full_name)
        .scalar_subquery()
    )
    return await session.scalar(
        select(func.count(ReviewJob.id)).where(ReviewJob.repository_id == repo_id_subq)
    ) or 0


# ── Queries ────────────────────────────────────────────────────────────────────


async def list_reviews(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    status: str | None = None,
    repository_full_name: str | None = None,
) -> list[dict[str, Any]]:
    """Return a flat list of review job rows joined with repo, PR, and summary."""
    q = (
        select(ReviewJob, Repository, PullRequest, ReviewSummary)
        .join(Repository, ReviewJob.repository_id == Repository.id)
        .join(PullRequest, ReviewJob.pull_request_id == PullRequest.id)
        .outerjoin(ReviewSummary, ReviewJob.id == ReviewSummary.review_job_id)
        .order_by(ReviewJob.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status:
        q = q.where(ReviewJob.status == status)
    if repository_full_name:
        q = q.where(Repository.full_name == repository_full_name)

    rows = (await session.execute(q)).all()

    return [
        {
            "delivery_id": job.delivery_id,
            "repository": repo.full_name,
            "pr_number": pr.pr_number,
            "title": pr.title,
            "author": pr.author,
            "status": job.status,
            "verdict": summary.verdict if summary else None,
            "risk_level": summary.risk_level if summary else None,
            "severity_score": summary.severity_score if summary else None,
            "provider": job.provider,
            "model": job.model,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "duration_ms": job.duration_ms,
            "created_at": job.created_at,
        }
        for job, repo, pr, summary in rows
    ]


async def get_review_detail(
    session: AsyncSession,
    delivery_id: str,
    findings_limit: int | None = 50,
    findings_offset: int = 0,
) -> dict[str, Any] | None:
    """
    Return a fully-loaded review detail dict using 3 queries instead of 6.

    Query 1: job + repository + PR + summary + submission (one 5-table join).
    Query 2: findings total count.
    Query 3: paginated findings slice.

    Pass findings_limit=None to load all findings (used by the /result fallback).
    """
    # Query 1 — main join
    row = (
        await session.execute(
            select(ReviewJob, Repository, PullRequest, ReviewSummary, ReviewSubmission)
            .join(Repository, ReviewJob.repository_id == Repository.id)
            .join(PullRequest, ReviewJob.pull_request_id == PullRequest.id)
            .outerjoin(ReviewSummary, ReviewJob.id == ReviewSummary.review_job_id)
            .outerjoin(ReviewSubmission, ReviewJob.id == ReviewSubmission.review_job_id)
            .where(ReviewJob.delivery_id == delivery_id)
        )
    ).first()

    if row is None:
        return None

    job, repo, pr, summary, submission = row

    # Query 2 — findings total
    findings_total: int = await session.scalar(
        select(func.count(ReviewFinding.id)).where(
            ReviewFinding.review_job_id == job.id
        )
    ) or 0

    # Query 3 — findings page
    findings_q = (
        select(ReviewFinding)
        .where(ReviewFinding.review_job_id == job.id)
        .order_by(ReviewFinding.severity, ReviewFinding.file_path)
    )
    if findings_limit is not None:
        findings_q = findings_q.limit(findings_limit).offset(findings_offset)

    findings = list((await session.execute(findings_q)).scalars().all())

    return {
        "job": job,
        "repository": repo,
        "pull_request": pr,
        "summary": summary,
        "findings": findings,
        "findings_total": findings_total,
        "findings_limit": findings_limit if findings_limit is not None else findings_total,
        "findings_offset": findings_offset,
        "submission": submission,
    }


async def list_repository_reviews(
    session: AsyncSession,
    full_name: str,
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return reviews for one repository using a single JOIN query."""
    q = (
        select(ReviewJob, PullRequest, ReviewSummary)
        .join(Repository, ReviewJob.repository_id == Repository.id)
        .join(PullRequest, ReviewJob.pull_request_id == PullRequest.id)
        .outerjoin(ReviewSummary, ReviewJob.id == ReviewSummary.review_job_id)
        .where(Repository.full_name == full_name)
        .order_by(ReviewJob.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    return [
        {
            "delivery_id": job.delivery_id,
            "pr_number": pr.pr_number,
            "title": pr.title,
            "author": pr.author,
            "status": job.status,
            "verdict": summary.verdict if summary else None,
            "risk_level": summary.risk_level if summary else None,
            "severity_score": summary.severity_score if summary else None,
            "provider": job.provider,
            "model": job.model,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "duration_ms": job.duration_ms,
            "created_at": job.created_at,
        }
        for job, pr, summary in (await session.execute(q)).all()
    ]
