"""
Analytics aggregate endpoints — powers the dashboard charts and metric cards.

All queries hit PostgreSQL directly (no Redis).  Each endpoint returns
zeroes when the database is empty so the dashboard renders gracefully.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_auth
from app.db.session import get_db
from app.models.review_finding import ReviewFinding
from app.models.review_job import ReviewJob
from app.models.review_summary import ReviewSummary

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[Depends(require_api_auth)],
)


# ── Response schemas ───────────────────────────────────────────────────────────


class AnalyticsOverview(BaseModel):
    total_reviews: int
    total_repositories: int
    completed_reviews: int
    failed_reviews: int
    success_rate: float
    total_findings: int
    critical_findings: int
    high_findings: int
    average_severity_score: float
    average_duration_ms: float


class DailyReview(BaseModel):
    date: str
    reviews: int
    completed: int
    failed: int


class ReviewsPerDayResponse(BaseModel):
    items: list[DailyReview]


class SeverityDistribution(BaseModel):
    critical: int
    high: int
    medium: int
    low: int


class VerdictDistribution(BaseModel):
    approve: int
    comment: int
    request_changes: int


class DailyRisk(BaseModel):
    date: str
    average_severity_score: float


class RiskTrendResponse(BaseModel):
    items: list[DailyRisk]


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get("/overview", response_model=AnalyticsOverview)
async def get_overview(
    session: AsyncSession = Depends(get_db),
) -> AnalyticsOverview:
    """Aggregate metrics for the dashboard hero cards."""
    # Single query: all job-level stats
    job_row = (
        await session.execute(
            select(
                func.count(ReviewJob.id).label("total"),
                func.count(func.distinct(ReviewJob.repository_id)).label("repos"),
                func.count(ReviewJob.id)
                .filter(ReviewJob.status == "completed")
                .label("completed"),
                func.count(ReviewJob.id)
                .filter(ReviewJob.status == "failed")
                .label("failed"),
                func.avg(ReviewJob.duration_ms).label("avg_duration"),
            )
        )
    ).first()

    # Single query: finding-level stats
    finding_row = (
        await session.execute(
            select(
                func.count(ReviewFinding.id).label("total"),
                func.count(ReviewFinding.id)
                .filter(ReviewFinding.severity == "critical")
                .label("critical"),
                func.count(ReviewFinding.id)
                .filter(ReviewFinding.severity == "high")
                .label("high"),
            )
        )
    ).first()

    # Single query: average severity score
    avg_score = await session.scalar(
        select(func.avg(ReviewSummary.severity_score))
    )

    total = job_row.total or 0
    completed = job_row.completed or 0
    failed = job_row.failed or 0
    success_rate = round((completed / total * 100), 1) if total > 0 else 0.0

    return AnalyticsOverview(
        total_reviews=total,
        total_repositories=job_row.repos or 0,
        completed_reviews=completed,
        failed_reviews=failed,
        success_rate=success_rate,
        total_findings=finding_row.total or 0,
        critical_findings=finding_row.critical or 0,
        high_findings=finding_row.high or 0,
        average_severity_score=round(float(avg_score or 0), 1),
        average_duration_ms=round(float(job_row.avg_duration or 0), 0),
    )


@router.get("/reviews-per-day", response_model=ReviewsPerDayResponse)
async def get_reviews_per_day(
    days: int = Query(14, ge=1, le=90),
    session: AsyncSession = Depends(get_db),
) -> ReviewsPerDayResponse:
    """Daily review counts for the time-series area chart."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        await session.execute(
            select(
                cast(ReviewJob.created_at, Date).label("review_date"),
                func.count(ReviewJob.id).label("reviews"),
                func.count(ReviewJob.id)
                .filter(ReviewJob.status == "completed")
                .label("completed"),
                func.count(ReviewJob.id)
                .filter(ReviewJob.status == "failed")
                .label("failed"),
            )
            .where(ReviewJob.created_at >= cutoff)
            .group_by(cast(ReviewJob.created_at, Date))
            .order_by(cast(ReviewJob.created_at, Date))
        )
    ).all()

    # Fill missing dates with zeros so charts always span the full range.
    db_by_date = {str(row.review_date): row for row in rows}

    # Use UTC date to stay consistent with the UTC cutoff above.
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days - 1)
    items: list[DailyReview] = []
    current = start_date
    while current <= end_date:
        d = str(current)
        row = db_by_date.get(d)
        items.append(
            DailyReview(
                date=d,
                reviews=row.reviews if row else 0,
                completed=row.completed if row else 0,
                failed=row.failed if row else 0,
            )
        )
        current += timedelta(days=1)

    return ReviewsPerDayResponse(items=items)


@router.get("/severity-distribution", response_model=SeverityDistribution)
async def get_severity_distribution(
    session: AsyncSession = Depends(get_db),
) -> SeverityDistribution:
    """Finding counts by severity for the donut chart."""
    rows = (
        await session.execute(
            select(
                ReviewFinding.severity.label("sev"),
                func.count(ReviewFinding.id).label("cnt"),
            ).group_by(ReviewFinding.severity)
        )
    ).all()

    data = {row.sev: row.cnt for row in rows}
    return SeverityDistribution(
        critical=data.get("critical", 0),
        high=data.get("high", 0),
        medium=data.get("medium", 0),
        low=data.get("low", 0),
    )


@router.get("/verdict-distribution", response_model=VerdictDistribution)
async def get_verdict_distribution(
    session: AsyncSession = Depends(get_db),
) -> VerdictDistribution:
    """Review verdicts distribution for the donut chart."""
    rows = (
        await session.execute(
            select(
                ReviewSummary.verdict.label("verdict"),
                func.count(ReviewSummary.id).label("cnt"),
            ).group_by(ReviewSummary.verdict)
        )
    ).all()

    data = {row.verdict: row.cnt for row in rows}
    return VerdictDistribution(
        approve=data.get("approve", 0),
        comment=data.get("comment", 0),
        request_changes=data.get("request_changes", 0),
    )


@router.get("/risk-trend", response_model=RiskTrendResponse)
async def get_risk_trend(
    days: int = Query(14, ge=1, le=90),
    session: AsyncSession = Depends(get_db),
) -> RiskTrendResponse:
    """Daily average severity scores for the risk trend line chart."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        await session.execute(
            select(
                cast(ReviewSummary.created_at, Date).label("review_date"),
                func.avg(ReviewSummary.severity_score).label("avg_score"),
            )
            .where(ReviewSummary.created_at >= cutoff)
            .group_by(cast(ReviewSummary.created_at, Date))
            .order_by(cast(ReviewSummary.created_at, Date))
        )
    ).all()

    db_by_date = {str(row.review_date): row for row in rows}

    # Use UTC date to stay consistent with the UTC cutoff above.
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days - 1)
    items: list[DailyRisk] = []
    current = start_date
    while current <= end_date:
        d = str(current)
        row = db_by_date.get(d)
        items.append(
            DailyRisk(
                date=d,
                average_severity_score=round(float(row.avg_score), 1) if row else 0.0,
            )
        )
        current += timedelta(days=1)

    return RiskTrendResponse(items=items)
