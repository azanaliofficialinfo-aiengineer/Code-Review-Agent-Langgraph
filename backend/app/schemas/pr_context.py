from pydantic import BaseModel, Field


class PullRequestMetadata(BaseModel):
    owner: str
    repo: str
    repository_full_name: str
    pr_number: int
    title: str
    author: str
    base_branch: str
    head_branch: str
    base_sha: str
    head_sha: str
    html_url: str
    installation_id: int


class ChangedFile(BaseModel):
    filename: str
    status: str  # added | removed | modified | renamed | copied | changed | unchanged
    additions: int
    deletions: int
    changes: int
    patch: str | None = None       # None for binary files
    raw_url: str = ""
    blob_url: str = ""
    is_binary: bool = False


class PRContext(BaseModel):
    delivery_id: str
    event_action: str
    metadata: PullRequestMetadata
    changed_files: list[ChangedFile] = Field(default_factory=list)
    total_files: int = 0
    total_additions: int = 0
    total_deletions: int = 0
