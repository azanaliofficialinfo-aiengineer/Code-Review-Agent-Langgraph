"""
Repository CRUD — idempotent upserts keyed on full_name.
"""
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repository import Repository


async def upsert_repository(
    session: AsyncSession,
    owner: str,
    name: str,
    full_name: str,
    installation_id: int,
    github_repo_id: int | None = None,
    default_branch: str | None = None,
) -> Repository:
    """
    Insert or update the repository row keyed on full_name.

    On conflict: updates installation_id and updated_at only.
    Returns the current state of the row.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        pg_insert(Repository)
        .values(
            owner=owner,
            name=name,
            full_name=full_name,
            installation_id=installation_id,
            github_repo_id=github_repo_id,
            default_branch=default_branch,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["full_name"],
            set_={
                "installation_id": installation_id,
                "github_repo_id": github_repo_id,
                "default_branch": default_branch,
                "updated_at": now,
            },
        )
    )
    await session.execute(stmt)
    await session.flush()

    result = await session.execute(
        select(Repository).where(Repository.full_name == full_name)
    )
    return result.scalar_one()


async def list_repositories(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> list[Repository]:
    result = await session.execute(
        select(Repository)
        .order_by(Repository.full_name)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_repository_by_full_name(
    session: AsyncSession,
    full_name: str,
) -> Repository | None:
    result = await session.execute(
        select(Repository).where(Repository.full_name == full_name)
    )
    return result.scalar_one_or_none()


async def count_repositories(session: AsyncSession) -> int:
    return await session.scalar(select(func.count(Repository.id))) or 0
