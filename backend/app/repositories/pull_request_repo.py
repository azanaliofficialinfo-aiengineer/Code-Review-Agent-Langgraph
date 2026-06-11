"""
PullRequest CRUD — idempotent upserts keyed on (repository_id, pr_number).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pull_request import PullRequest


async def upsert_pull_request(
    session: AsyncSession,
    repository_id: uuid.UUID,
    pr_number: int,
    title: str | None = None,
    author: str | None = None,
    base_branch: str | None = None,
    head_branch: str | None = None,
    base_sha: str | None = None,
    head_sha: str | None = None,
    html_url: str | None = None,
    state: str | None = None,
) -> PullRequest:
    """
    Insert or update the PR row keyed on (repository_id, pr_number).

    On conflict: updates mutable fields (SHAs, state, title) and updated_at.
    Returns the current state of the row.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        pg_insert(PullRequest)
        .values(
            repository_id=repository_id,
            pr_number=pr_number,
            title=title,
            author=author,
            base_branch=base_branch,
            head_branch=head_branch,
            base_sha=base_sha,
            head_sha=head_sha,
            html_url=html_url,
            state=state,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            constraint="uq_pull_requests_repo_pr",
            set_={
                "title": title,
                "head_sha": head_sha,
                "base_sha": base_sha,
                "state": state,
                "html_url": html_url,
                "updated_at": now,
            },
        )
    )
    await session.execute(stmt)
    await session.flush()

    result = await session.execute(
        select(PullRequest).where(
            PullRequest.repository_id == repository_id,
            PullRequest.pr_number == pr_number,
        )
    )
    return result.scalar_one()
