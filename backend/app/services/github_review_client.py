"""
GitHub Pull Request Review API client.

Submits a fully-built ReviewSubmission to the GitHub Reviews endpoint:
    POST /repos/{owner}/{repo}/pulls/{pr_number}/reviews

Authentication uses the existing GitHub App installation token flow
(app.services.github_auth).  The bearer token is never logged.

This module is only called when GITHUB_DRY_RUN=false.  In dry-run mode the
worker stores the payload in Redis and skips calling this module entirely.
"""
import logging

import httpx

from app.core.exceptions import GitHubAPIError, GitHubAuthError
from app.schemas.github_review import ReviewSubmission
from app.services.github_auth import get_installation_access_token

logger = logging.getLogger(__name__)

_GITHUB_API_BASE = "https://api.github.com"
_GITHUB_ACCEPT   = "application/vnd.github+json"
_GITHUB_VERSION  = "2022-11-28"
_REQUEST_TIMEOUT = 30.0


async def submit_review(
    owner: str,
    repo: str,
    pr_number: int,
    installation_id: int,
    review_submission: ReviewSubmission,
) -> dict:
    """
    Post a pull-request review to GitHub.

    Parameters
    ----------
    owner:
        Repository owner (user or organisation name).
    repo:
        Repository name (without the owner prefix).
    pr_number:
        Pull-request number.
    installation_id:
        GitHub App installation ID — used to obtain a bearer token.
    review_submission:
        The fully-built payload produced by ``build_review_submission``.

    Returns
    -------
    dict
        The GitHub API response body (review object).

    Raises
    ------
    GitHubAuthError
        If the installation access token cannot be obtained.
    GitHubAPIError
        If the GitHub API returns a non-2xx response.
    """
    # Obtain a short-lived installation token.  Value is never logged.
    token = await get_installation_access_token(installation_id)

    url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"

    # Convert internal inline comment objects to GitHub's expected shape.
    # side="RIGHT" targets added/modified lines (modern line-based API).
    github_comments = [
        {
            "path": c.file_path,
            "line": c.line,
            "body": c.body,
            "side": "RIGHT",
        }
        for c in review_submission.comments
    ]

    payload: dict = {
        "commit_id": review_submission.commit_id,
        "body": review_submission.body,
        "event": review_submission.event,
        "comments": github_comments,
    }

    logger.info(
        "[GitHubReview] Submitting review: owner=%s repo=%s pr=%d event=%s inline_comments=%d",
        owner, repo, pr_number, review_submission.event, len(github_comments),
    )

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        response = await client.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": _GITHUB_ACCEPT,
                "X-GitHub-Api-Version": _GITHUB_VERSION,
            },
        )

    if not response.is_success:
        msg = _extract_message(response)
        logger.error(
            "[GitHubReview] API error: owner=%s repo=%s pr=%d status=%d",
            owner, repo, pr_number, response.status_code,
        )
        raise GitHubAPIError(response.status_code, msg, url)

    logger.info(
        "[GitHubReview] Review posted successfully: owner=%s repo=%s pr=%d",
        owner, repo, pr_number,
    )
    return response.json()


def _extract_message(response: httpx.Response) -> str:
    """Pull the human-readable message from a GitHub error response body."""
    try:
        return response.json().get("message", response.text[:300])
    except Exception:
        return response.text[:300]
