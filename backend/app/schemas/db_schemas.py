"""
Response schemas for database-backed review endpoints.

These are Pydantic models that shape the JSON returned by:
  GET /reviews
  GET /reviews/{delivery_id}
  GET /repositories
  GET /repositories/{owner}/{repo}/reviews
"""
from datetime import datetime

from pydantic import BaseModel


class RepositoryInfo(BaseModel):
    owner: str
    name: str
    full_name: str
    installation_id: int
    default_branch: str | None
    is_active: bool


class PullRequestInfo(BaseModel):
    pr_number: int
    title: str | None
    author: str | None
    base_branch: str | None
    head_branch: str | None
    base_sha: str | None
    head_sha: str | None
    html_url: str | None
    state: str | None


class SummaryInfo(BaseModel):
    verdict: str
    risk_level: str
    severity_score: int
    summary_text: str
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int


class FindingInfo(BaseModel):
    file_path: str
    line: int | None
    severity: str
    category: str
    title: str
    description: str
    suggestion: str
    confidence: float
    should_comment: bool


class SubmissionInfo(BaseModel):
    event: str
    commit_id: str
    dry_run: bool
    submitted_to_github: bool
    inline_comment_count: int
    github_review_id: int | None
    created_at: datetime


# ── Paginated wrappers ─────────────────────────────────────────────────────────


class PaginatedFindingList(BaseModel):
    """Paginated slice of findings inside a ReviewDetail response."""
    items: list[FindingInfo]
    total: int
    limit: int
    offset: int


class ReviewListItem(BaseModel):
    delivery_id: str
    repository: str
    pr_number: int
    title: str | None
    author: str | None
    status: str
    verdict: str | None
    risk_level: str | None
    severity_score: int | None
    provider: str | None
    model: str | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    created_at: datetime


class ReviewDetail(BaseModel):
    delivery_id: str
    status: str
    provider: str | None
    model: str | None
    event_action: str | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    error_message: str | None
    created_at: datetime
    repository: RepositoryInfo
    pull_request: PullRequestInfo
    summary: SummaryInfo | None
    findings: PaginatedFindingList
    submission: SubmissionInfo | None


class PaginatedReviews(BaseModel):
    """Paginated response for GET /reviews."""
    items: list[ReviewListItem]
    total: int
    limit: int
    offset: int


class RepositoryListItem(BaseModel):
    full_name: str
    owner: str
    name: str
    installation_id: int
    is_active: bool
    total_reviews: int
    last_review_at: datetime | None


class PaginatedRepositories(BaseModel):
    """Paginated response for GET /repositories."""
    items: list[RepositoryListItem]
    total: int
    limit: int
    offset: int


class PaginatedRepositoryReviews(BaseModel):
    """Paginated response for GET /repositories/{owner}/{repo}/reviews."""
    items: list[ReviewListItem]
    total: int
    limit: int
    offset: int
