"""
Repository listing endpoints.

GET /repositories                          — list all known repositories with stats
GET /repositories/{owner}/{repo}/reviews  — reviews for a specific repository
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_auth
from app.db.session import get_db
from app.models.repository import Repository
from app.models.review_job import ReviewJob
from app.repositories.repository_repo import (
    count_repositories as _count_repositories,
    get_repository_by_full_name,
)
from app.repositories.review_job_repo import (
    count_repository_reviews as _count_repository_reviews,
    list_repository_reviews,
)
from app.schemas.db_schemas import (
    PaginatedRepositories,
    PaginatedRepositoryReviews,
    RepositoryListItem,
    ReviewListItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repositories", tags=["repositories"])


# ── GET /repositories ──────────────────────────────────────────────────────────

@router.get(
    "",
    summary="List all known repositories with review stats",
    response_model=PaginatedRepositories,
    dependencies=[Depends(require_api_auth)],
)
async def list_repositories_endpoint(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> PaginatedRepositories:
    """
    Return all repositories the agent has reviewed, with total review count
    and the timestamp of the most recent review.
    """
    stats_subq = (
        select(
            ReviewJob.repository_id,
            func.count(ReviewJob.id).label("total_reviews"),
            func.max(ReviewJob.created_at).label("last_review_at"),
        )
        .group_by(ReviewJob.repository_id)
        .subquery()
    )

    q = (
        select(
            Repository,
            func.coalesce(stats_subq.c.total_reviews, 0).label("total_reviews"),
            stats_subq.c.last_review_at,
        )
        .outerjoin(stats_subq, Repository.id == stats_subq.c.repository_id)
        .order_by(Repository.full_name)
        .limit(limit)
        .offset(offset)
    )

    rows = (await session.execute(q)).all()
    total = await _count_repositories(session)

    return PaginatedRepositories(
        items=[
            RepositoryListItem(
                full_name=repo.full_name,
                owner=repo.owner,
                name=repo.name,
                installation_id=repo.installation_id,
                is_active=repo.is_active,
                total_reviews=int(total_r),
                last_review_at=last_at,
            )
            for repo, total_r, last_at in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


# ── GET /repositories/{owner}/{repo}/reviews ──────────────────────────────────

@router.get(
    "/{owner}/{repo}/reviews",
    summary="List reviews for a specific repository",
    response_model=PaginatedRepositoryReviews,
    dependencies=[Depends(require_api_auth)],
)
async def list_repository_reviews_endpoint(
    owner: str,
    repo: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> PaginatedRepositoryReviews:
    """
    Return paginated review jobs for one repository, newest first.

    Returns 404 if the repository has never been reviewed.
    """
    full_name = f"{owner}/{repo}"

    existing = await get_repository_by_full_name(session, full_name)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"Repository '{full_name}' not found.",
        )

    rows, total = (
        await list_repository_reviews(session, full_name, limit=limit, offset=offset),
        await _count_repository_reviews(session, full_name),
    )

    return PaginatedRepositoryReviews(
        items=[ReviewListItem(**row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
