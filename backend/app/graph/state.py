"""
LangGraph review pipeline state.

All fields are JSON-serializable so the state can be snapshotted to Redis
at any point during graph execution.

pr_context and review_result are stored as plain dicts (model_dump() output)
rather than Pydantic instances so that LangGraph can merge partial updates
without deep-copy issues.
"""
from typing import Literal, TypedDict

# Exhaustive set of valid status values.
# Routing functions compare against these; a typo here is a type error, not a
# silent routing failure.
ReviewStatus = Literal[
    "queued",
    "fetching_context",
    "reviewing",
    "completed",
    "failed",
]


class ReviewState(TypedDict):
    delivery_id: str
    status: ReviewStatus
    pr_context: dict | None        # PRContext.model_dump(), populated after fetch_context
    review_result: dict | None     # ReviewResult.model_dump(), populated after review_pr
    started_at: str | None         # ISO-8601 datetime string
    completed_at: str | None       # ISO-8601 datetime string
    error: str | None              # human-readable error, set on failure
