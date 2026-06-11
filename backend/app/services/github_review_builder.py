"""
GitHub review payload builder.

Converts a ReviewResult + graph state dict into a ReviewSubmission that is
ready to be stored (dry-run) or posted to the GitHub Pull Requests API.

Design contract
---------------
- Pure function: no I/O, no side effects, no network calls.
- Raises ValueError for missing required graph-state fields so the caller
  can log and skip gracefully.
- Inline comments are created only for findings where both conditions hold:
    1. finding.should_comment is True
    2. finding.line is not None and > 0
  All other findings are reflected in the aggregate summary only.
"""
from typing import Literal

from app.schemas.github_review import InlineReviewComment, ReviewSubmission
from app.schemas.review_result import ReviewFinding, ReviewResult, ReviewSummary

# ── Severity helpers ──────────────────────────────────────────────────────────

_SEVERITY_ICON: dict[str, str] = {
    "critical": "🔴",
    "high": "⚠️",
    "medium": "🟡",
    "low": "ℹ️",
}

_CATEGORY_LABEL: dict[str, str] = {
    "security": "Security",
    "logic_bug": "Logic Bug",
    "performance": "Performance",
    "maintainability": "Maintainability",
    "test_coverage": "Test Coverage",
    "style": "Style",
}


def _category_label(category: str) -> str:
    return _CATEGORY_LABEL.get(category, category.replace("_", " ").title())


# ── Event derivation ──────────────────────────────────────────────────────────

def _derive_event(summary: ReviewSummary) -> Literal["COMMENT", "REQUEST_CHANGES", "APPROVE"]:
    """
    Derive the GitHub review event from finding counts.

    Rules (spec-defined):
      critical or high findings present  →  REQUEST_CHANGES
      medium findings only               →  COMMENT
      no actionable findings             →  APPROVE
    """
    if summary.critical_count > 0 or summary.high_count > 0:
        return "REQUEST_CHANGES"
    if summary.medium_count > 0:
        return "COMMENT"
    return "APPROVE"


# ── Comment body builder ──────────────────────────────────────────────────────

def _build_comment_body(finding: ReviewFinding) -> str:
    """
    Format a single inline review comment body.

    Example output:
        ⚠️ High — Security

        Potential SQL injection risk detected.

        Suggestion:
        Use parameterized queries.

        Confidence: 91%
    """
    icon = _SEVERITY_ICON.get(finding.severity, "•")
    category = _category_label(finding.category)
    confidence_pct = round(finding.confidence * 100)

    parts: list[str] = [
        f"{icon} {finding.severity.capitalize()} — {category}",
        "",
        finding.description,
    ]
    if finding.suggestion:
        parts += [
            "",
            "Suggestion:",
            finding.suggestion,
        ]
    parts += [
        "",
        f"Confidence: {confidence_pct}%",
    ]
    return "\n".join(parts)


# ── Summary body builder ──────────────────────────────────────────────────────

def _build_summary_body(result: ReviewResult, event: str) -> str:
    """
    Format the review-level summary body posted at the top of the GitHub review.

    Example output:
        ## 🤖 CodeReview Agent Review

        Verdict: REQUEST_CHANGES

        Risk Level: High

        Severity Score: 67/100

        Findings:
        * Critical: 2
        * High: 5
        * Medium: 1
        * Low: 0

        Summary:
        The authentication module introduces a SQL injection vector…
    """
    s = result.summary
    risk_label = s.risk_level.capitalize()

    lines: list[str] = [
        "## 🤖 CodeReview Agent Review",
        "",
        f"Verdict: {event}",
        "",
        f"Risk Level: {risk_label}",
        "",
        f"Severity Score: {s.severity_score}/100",
        "",
        "Findings:",
        f"* Critical: {s.critical_count}",
        f"* High: {s.high_count}",
        f"* Medium: {s.medium_count}",
        f"* Low: {s.low_count}",
        "",
        "Summary:",
        s.summary_text,
    ]
    return "\n".join(lines)


# ── Main builder ──────────────────────────────────────────────────────────────

def build_review_submission(result: ReviewResult, graph_state: dict) -> ReviewSubmission:
    """
    Convert a ReviewResult and stored graph state into a ReviewSubmission.

    Parameters
    ----------
    result:
        The completed ReviewResult from the LangGraph review pipeline.
    graph_state:
        The dict returned by ``get_graph_state(delivery_id)``.  Must contain
        owner, repo, pr_number, and head_sha (all persisted in Phase 5.5).

    Raises
    ------
    ValueError
        If any required graph-state field is absent or None.
    """
    # ── Extract required fields from graph state ───────────────────────────
    missing = [
        f for f in ("owner", "repo", "pr_number", "head_sha")
        if not graph_state.get(f)
    ]
    if missing:
        raise ValueError(
            f"Graph state is missing required fields for review submission: {missing} "
            f"(delivery_id={graph_state.get('delivery_id')})"
        )

    owner: str = graph_state["owner"]
    repo: str = graph_state["repo"]
    pr_number: int = int(graph_state["pr_number"])
    commit_id: str = graph_state["head_sha"]
    repository: str = graph_state.get("repository") or f"{owner}/{repo}"

    # ── Determine GitHub review event ──────────────────────────────────────
    event = _derive_event(result.summary)

    # ── Build inline comments ──────────────────────────────────────────────
    # Only for findings that are comment-worthy AND have a valid line number.
    inline_comments: list[InlineReviewComment] = []
    for finding in result.findings:
        if not finding.should_comment:
            continue
        if finding.line is None or finding.line <= 0:
            continue
        inline_comments.append(
            InlineReviewComment(
                file_path=finding.file_path,
                line=finding.line,
                body=_build_comment_body(finding),
                severity=finding.severity,
                category=finding.category,
            )
        )

    # ── Build review summary body ──────────────────────────────────────────
    body = _build_summary_body(result, event)

    return ReviewSubmission(
        repository=repository,
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        commit_id=commit_id,
        event=event,
        body=body,
        comments=inline_comments,
    )
