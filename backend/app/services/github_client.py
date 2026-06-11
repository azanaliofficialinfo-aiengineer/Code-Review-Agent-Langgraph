"""
Thin async wrapper around the GitHub REST API.

All functions accept a pre-obtained installation access token — authentication
is handled upstream in github_auth.py.  This module is intentionally stateless:
no token caching, no singleton client (both can be added in Phase 5).
"""
import logging

import httpx

from app.core.exceptions import GitHubAPIError

logger = logging.getLogger(__name__)

_GITHUB_API_BASE = "https://api.github.com"
_DEFAULT_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
_PAGE_SIZE = 100   # GitHub's max per_page for PR files


def _auth_headers(token: str) -> dict[str, str]:
    return {**_DEFAULT_HEADERS, "Authorization": f"Bearer {token}"}


def _raise_for_status(response: httpx.Response, url: str) -> None:
    """Convert a non-2xx GitHub response into a typed GitHubAPIError."""
    if response.is_success:
        return
    try:
        message = response.json().get("message", response.text[:300])
    except Exception:
        message = response.text[:300]
    raise GitHubAPIError(response.status_code, message, url)


async def get_pull_request(
    owner: str,
    repo: str,
    pr_number: int,
    token: str,
) -> dict:
    """
    Fetch full PR metadata.

    GET /repos/{owner}/{repo}/pulls/{pull_number}
    """
    url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
    logger.debug("Fetching PR metadata: %s", url)

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, headers=_auth_headers(token))

    _raise_for_status(response, url)
    return response.json()


async def get_pull_request_files(
    owner: str,
    repo: str,
    pr_number: int,
    token: str,
) -> list[dict]:
    """
    Fetch all files changed in a PR, following pagination automatically.

    GET /repos/{owner}/{repo}/pulls/{pull_number}/files
    GitHub returns at most 3 000 files; large PRs will page through all of them.
    """
    base_url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"
    all_files: list[dict] = []
    page = 1

    async with httpx.AsyncClient(timeout=20.0) as client:
        while True:
            url = f"{base_url}?per_page={_PAGE_SIZE}&page={page}"
            logger.debug("Fetching PR files page %d: %s", page, base_url)

            response = await client.get(url, headers=_auth_headers(token))
            _raise_for_status(response, url)

            batch: list[dict] = response.json()
            all_files.extend(batch)

            if len(batch) < _PAGE_SIZE:
                break  # last page — no more results

            page += 1

    logger.debug("Retrieved %d changed files for %s/%s#%d", len(all_files), owner, repo, pr_number)
    return all_files
