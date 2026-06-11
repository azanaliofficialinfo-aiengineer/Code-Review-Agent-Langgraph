"""
GitHub review submission schemas.

Defines the payload shapes that travel between the review builder,
submission store, dedup service, and GitHub review API client.
"""
from typing import Literal

from pydantic import BaseModel


class InlineReviewComment(BaseModel):
    """A single line-level comment targeting a specific file and line number."""

    file_path: str
    line: int
    body: str
    severity: str
    category: str


class ReviewSubmission(BaseModel):
    """
    A fully-built GitHub pull-request review payload.

    This is the object that is either stored (dry-run) or posted to
    POST /repos/{owner}/{repo}/pulls/{pr_number}/reviews.

    ``event`` must be one of the three values GitHub accepts:
      - COMMENT         — general comment, no approval decision
      - REQUEST_CHANGES — blocks merge until changes are addressed
      - APPROVE         — signals no blocking issues
    """

    repository: str       # full name, e.g. "owner/repo"
    owner: str
    repo: str
    pr_number: int
    commit_id: str        # head_sha of the PR
    event: Literal["COMMENT", "REQUEST_CHANGES", "APPROVE"]
    body: str             # markdown summary posted as the review body
    comments: list[InlineReviewComment]
