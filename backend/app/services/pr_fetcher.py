"""
PR context builder.

Reads a stored webhook payload from Redis, authenticates as the GitHub App,
fetches PR metadata + changed files, and returns a fully hydrated PRContext
ready for the AI review pipeline (Phase 4+).
"""
import logging

from app.core.exceptions import (
    DeliveryNotFoundError,
    GitHubAPIError,
    MissingInstallationError,
)
from app.schemas.pr_context import ChangedFile, PRContext, PullRequestMetadata
from app.services.github_auth import get_installation_access_token
from app.services.github_client import get_pull_request, get_pull_request_files
from app.services.redis_service import get_webhook_payload

logger = logging.getLogger(__name__)


async def build_pr_context_from_delivery(delivery_id: str) -> PRContext:
    """
    Construct a PRContext from a webhook delivery that was previously stored in Redis.

    Steps
    -----
    1. Load raw webhook record from Redis.
    2. Extract owner, repo, PR number, installation ID, and action.
    3. Obtain an installation access token.
    4. Fetch PR metadata and changed files from GitHub.
    5. Map API responses into typed Pydantic models.
    6. Return the assembled PRContext.

    Raises:
        DeliveryNotFoundError:  delivery_id not in Redis (expired or never stored).
        MissingInstallationError: payload lacks installation.id (non-App webhook).
        GitHubAPIError:         GitHub API request failed.
    """
    # ── 1. Load from Redis ─────────────────────────────────────────────────
    record = await get_webhook_payload(delivery_id)
    if record is None:
        raise DeliveryNotFoundError(delivery_id)

    raw: dict = record["raw_payload"]
    action: str = record.get("action", "")

    # ── 2. Extract coordinates ─────────────────────────────────────────────
    repo_full: str = raw.get("repository", {}).get("full_name", "")
    if "/" not in repo_full:
        raise ValueError(f"Cannot parse repository full_name from delivery '{delivery_id}': {repo_full!r}")

    owner, repo = repo_full.split("/", 1)
    pr_number: int = raw.get("pull_request", {}).get("number", 0)

    installation_id: int | None = raw.get("installation", {}).get("id")
    if not installation_id:
        raise MissingInstallationError(delivery_id)

    logger.info(
        "Building PR context for %s#%d (delivery=%s, action=%s)",
        repo_full, pr_number, delivery_id, action,
    )

    # ── 3. Authenticate ────────────────────────────────────────────────────
    token = await get_installation_access_token(installation_id)

    # ── 4. Fetch from GitHub ───────────────────────────────────────────────
    pr_data, files_data = await _fetch_pr_and_files(owner, repo, pr_number, token)

    # ── 5. Build typed models ──────────────────────────────────────────────
    metadata = _build_metadata(owner, repo, repo_full, pr_number, installation_id, pr_data)
    changed_files = _build_changed_files(files_data)

    # ── 6. Assemble context ────────────────────────────────────────────────
    return PRContext(
        delivery_id=delivery_id,
        event_action=action,
        metadata=metadata,
        changed_files=changed_files,
        total_files=len(changed_files),
        total_additions=sum(f.additions for f in changed_files),
        total_deletions=sum(f.deletions for f in changed_files),
    )


# ── Private helpers ────────────────────────────────────────────────────────────


async def _fetch_pr_and_files(
    owner: str,
    repo: str,
    pr_number: int,
    token: str,
) -> tuple[dict, list[dict]]:
    """Run PR metadata and files fetches; errors propagate as GitHubAPIError."""
    pr_data = await get_pull_request(owner, repo, pr_number, token)
    files_data = await get_pull_request_files(owner, repo, pr_number, token)
    return pr_data, files_data


def _build_metadata(
    owner: str,
    repo: str,
    repo_full: str,
    pr_number: int,
    installation_id: int,
    pr_data: dict,
) -> PullRequestMetadata:
    return PullRequestMetadata(
        owner=owner,
        repo=repo,
        repository_full_name=repo_full,
        pr_number=pr_number,
        title=pr_data.get("title", ""),
        author=pr_data.get("user", {}).get("login", ""),
        base_branch=pr_data.get("base", {}).get("ref", ""),
        head_branch=pr_data.get("head", {}).get("ref", ""),
        base_sha=pr_data.get("base", {}).get("sha", ""),
        head_sha=pr_data.get("head", {}).get("sha", ""),
        html_url=pr_data.get("html_url", ""),
        installation_id=installation_id,
    )


def _build_changed_files(files_data: list[dict]) -> list[ChangedFile]:
    files: list[ChangedFile] = []
    for entry in files_data:
        patch: str | None = entry.get("patch")  # absent for binary files
        files.append(
            ChangedFile(
                filename=entry.get("filename", ""),
                status=entry.get("status", ""),
                additions=entry.get("additions", 0),
                deletions=entry.get("deletions", 0),
                changes=entry.get("changes", 0),
                patch=patch,
                raw_url=entry.get("raw_url", ""),
                blob_url=entry.get("blob_url", ""),
                is_binary=patch is None,
            )
        )
    return files
