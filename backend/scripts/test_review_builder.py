#!/usr/bin/env python3
"""
Phase 6 review builder test suite.

Validates:
  1. Verdict mapping — critical/high -> REQUEST_CHANGES, medium -> COMMENT,
                       no findings -> APPROVE
  2. Summary body format — required sections present
  3. Inline comment generation — only should_comment=True + valid line
  4. Duplicate prevention — dedup lock (requires Redis)
  5. Dry-run payload storage — save -> retrieve (requires Redis)

Static tests (1-3) run on any Python version without Redis.
Runtime tests (4-5) require the project venv + a running Redis instance.

Usage
-----
    cd backend
    python scripts/test_review_builder.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os  # noqa: E402
os.environ.setdefault("GROQ_API_KEY", "test-key")

# ── Result tracking ────────────────────────────────────────────────────────────

_results: list[tuple[str, str, str]] = []

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


def record(name: str, status: str, detail: str = "") -> None:
    _results.append((name, status, detail))
    icon = {"PASS": ".", "FAIL": "F", "SKIP": "-"}[status]
    suffix = f" — {detail}" if detail else ""
    print(f"  {icon}  [{status}]  {name}{suffix}")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_finding(
    severity: str = "high",
    category: str = "security",
    confidence: float = 0.91,
    line: int | None = 42,
    description: str = "Potential SQL injection risk detected.",
    suggestion: str = "Use parameterized queries.",
) -> "ReviewFinding":
    from app.schemas.review_result import ReviewFinding  # noqa: PLC0415
    return ReviewFinding(
        file_path="src/auth.py",
        line=line,
        severity=severity,
        category=category,
        title="Test finding",
        description=description,
        suggestion=suggestion,
        confidence=confidence,
    )


def _make_summary(
    verdict: str = "request_changes",
    risk_level: str = "high",
    severity_score: int = 67,
    critical_count: int = 0,
    high_count: int = 0,
    medium_count: int = 0,
    low_count: int = 0,
    summary_text: str = "The authentication module introduces a risk.",
) -> "ReviewSummary":
    from app.schemas.review_result import ReviewSummary  # noqa: PLC0415
    total = critical_count + high_count + medium_count + low_count
    return ReviewSummary(
        verdict=verdict,
        risk_level=risk_level,
        severity_score=severity_score,
        summary_text=summary_text,
        total_findings=total,
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
    )


def _make_result(findings=(), **summary_kwargs) -> "ReviewResult":
    from app.schemas.review_result import ReviewResult  # noqa: PLC0415
    return ReviewResult(
        delivery_id="test-delivery-001",
        repository="owner/repo",
        pr_number=42,
        provider="groq",
        model="test-model",
        findings=list(findings),
        summary=_make_summary(**summary_kwargs),
        reviewed_files=["src/auth.py"],
        skipped_files=[],
    )


_GRAPH_STATE = {
    "delivery_id": "test-delivery-001",
    "owner": "owner",
    "repo": "repo",
    "pr_number": 42,
    "head_sha": "abc123def456",
    "repository": "owner/repo",
    "installation_id": 12345,
    "status": "completed",
}


# ── Static tests ───────────────────────────────────────────────────────────────

def test_verdict_request_changes_high() -> None:
    from app.services.github_review_builder import build_review_submission  # noqa: PLC0415
    finding = _make_finding(severity="high")
    result = _make_result(
        findings=[finding],
        verdict="request_changes",
        high_count=1,
    )
    sub = build_review_submission(result, _GRAPH_STATE)
    if sub.event == "REQUEST_CHANGES":
        record("verdict:high->REQUEST_CHANGES", PASS)
    else:
        record("verdict:high->REQUEST_CHANGES", FAIL, f"got {sub.event!r}")


def test_verdict_request_changes_critical() -> None:
    from app.services.github_review_builder import build_review_submission  # noqa: PLC0415
    finding = _make_finding(severity="critical")
    result = _make_result(
        findings=[finding],
        verdict="request_changes",
        risk_level="critical",
        severity_score=90,
        critical_count=1,
    )
    sub = build_review_submission(result, _GRAPH_STATE)
    if sub.event == "REQUEST_CHANGES":
        record("verdict:critical->REQUEST_CHANGES", PASS)
    else:
        record("verdict:critical->REQUEST_CHANGES", FAIL, f"got {sub.event!r}")


def test_verdict_comment_medium_only() -> None:
    from app.services.github_review_builder import build_review_submission  # noqa: PLC0415
    finding = _make_finding(severity="medium", category="performance")
    result = _make_result(
        findings=[finding],
        verdict="comment",
        risk_level="medium",
        severity_score=35,
        medium_count=1,
    )
    sub = build_review_submission(result, _GRAPH_STATE)
    if sub.event == "COMMENT":
        record("verdict:medium_only->COMMENT", PASS)
    else:
        record("verdict:medium_only->COMMENT", FAIL, f"got {sub.event!r}")


def test_verdict_approve_no_findings() -> None:
    from app.services.github_review_builder import build_review_submission  # noqa: PLC0415
    result = _make_result(
        findings=[],
        verdict="approve",
        risk_level="low",
        severity_score=0,
    )
    sub = build_review_submission(result, _GRAPH_STATE)
    if sub.event == "APPROVE":
        record("verdict:no_findings->APPROVE", PASS)
    else:
        record("verdict:no_findings->APPROVE", FAIL, f"got {sub.event!r}")


def test_summary_body_format() -> None:
    from app.services.github_review_builder import build_review_submission  # noqa: PLC0415
    finding = _make_finding()
    result = _make_result(
        findings=[finding],
        summary_text="The authentication module introduces a SQL injection vector.",
        high_count=1,
    )
    sub = build_review_submission(result, _GRAPH_STATE)
    body = sub.body

    checks = {
        "## 🤖 CodeReview Agent Review": "## header",
        "Verdict:": "Verdict field",
        "Risk Level:": "Risk Level field",
        "Severity Score:": "Severity Score field",
        "Findings:": "Findings section",
        "Summary:": "Summary section",
        "authentication module": "summary_text content",
    }
    missing = [label for marker, label in checks.items() if marker not in body]
    if not missing:
        record("summary:body_format", PASS, f"{len(checks)} expected sections present")
    else:
        record("summary:body_format", FAIL, f"missing sections: {missing}")


def test_inline_comment_eligible() -> None:
    """Finding with should_comment=True and valid line -> inline comment."""
    from app.services.github_review_builder import build_review_submission  # noqa: PLC0415
    finding = _make_finding(severity="high", confidence=0.91, line=42)
    # Confirm the validator set should_comment=True
    assert finding.should_comment, "Test setup error: expected should_comment=True"
    result = _make_result(findings=[finding], high_count=1)
    sub = build_review_submission(result, _GRAPH_STATE)
    if len(sub.comments) == 1 and sub.comments[0].line == 42:
        record("inline:eligible_finding->comment", PASS,
               f"line={sub.comments[0].line} file={sub.comments[0].file_path}")
    else:
        record("inline:eligible_finding->comment", FAIL,
               f"expected 1 comment, got {len(sub.comments)}")


def test_inline_comment_no_line() -> None:
    """Finding with should_comment=True but line=None -> no inline comment."""
    from app.services.github_review_builder import build_review_submission  # noqa: PLC0415
    finding = _make_finding(severity="high", confidence=0.91, line=None)
    assert finding.should_comment, "Test setup error: expected should_comment=True"
    result = _make_result(findings=[finding], high_count=1)
    sub = build_review_submission(result, _GRAPH_STATE)
    if len(sub.comments) == 0:
        record("inline:no_line->skipped", PASS)
    else:
        record("inline:no_line->skipped", FAIL,
               f"expected 0 comments, got {len(sub.comments)}")


def test_inline_comment_low_confidence() -> None:
    """Finding with confidence below threshold -> should_comment=False -> no inline comment."""
    from app.services.github_review_builder import build_review_submission  # noqa: PLC0415
    finding = _make_finding(severity="high", confidence=0.20, line=10)
    assert not finding.should_comment, "Test setup error: expected should_comment=False"
    result = _make_result(findings=[finding], high_count=1)
    sub = build_review_submission(result, _GRAPH_STATE)
    if len(sub.comments) == 0:
        record("inline:low_confidence->skipped", PASS)
    else:
        record("inline:low_confidence->skipped", FAIL,
               f"expected 0 comments, got {len(sub.comments)}")


def test_inline_comment_body_format() -> None:
    """Inline comment body contains severity, category, description, suggestion, confidence."""
    from app.services.github_review_builder import build_review_submission  # noqa: PLC0415
    finding = _make_finding(
        severity="high",
        category="security",
        confidence=0.91,
        line=42,
        description="Potential SQL injection risk detected.",
        suggestion="Use parameterized queries.",
    )
    result = _make_result(findings=[finding], high_count=1)
    sub = build_review_submission(result, _GRAPH_STATE)
    if not sub.comments:
        record("inline:comment_body_format", FAIL, "no inline comments generated")
        return
    body = sub.comments[0].body
    checks = {
        "High": "severity label",
        "Security": "category label",
        "Potential SQL injection": "description text",
        "Use parameterized queries": "suggestion text",
        "Confidence: 91%": "confidence percentage",
    }
    missing = [label for marker, label in checks.items() if marker not in body]
    if not missing:
        record("inline:comment_body_format", PASS, f"{len(checks)} elements present")
    else:
        record("inline:comment_body_format", FAIL, f"missing: {missing}")


def test_missing_graph_state_field() -> None:
    """build_review_submission raises ValueError when a required graph state field is absent."""
    from app.services.github_review_builder import build_review_submission  # noqa: PLC0415
    bad_state = {k: v for k, v in _GRAPH_STATE.items() if k != "head_sha"}
    result = _make_result()
    try:
        build_review_submission(result, bad_state)
        record("builder:missing_field_raises", FAIL, "ValueError was not raised")
    except ValueError as exc:
        if "head_sha" in str(exc):
            record("builder:missing_field_raises", PASS, str(exc)[:80])
        else:
            record("builder:missing_field_raises", FAIL,
                   f"ValueError raised but 'head_sha' not in message: {exc}")


# ── Runtime tests (require Redis) ─────────────────────────────────────────────

async def _redis_ping() -> bool:
    try:
        from app.services.redis_service import ping_redis  # noqa: PLC0415
        return await ping_redis()
    except Exception:
        return False


async def test_dedup_lock() -> None:
    """is_already_reviewed returns False before, True after mark_as_reviewed."""
    _TEST_ID = "test_dedup_phase6_temp"
    try:
        from app.services.comment_dedup import (  # noqa: PLC0415
            is_already_reviewed, mark_as_reviewed,
        )
        from app.services.redis_service import get_redis_client  # noqa: PLC0415
        from app.core.constants import REVIEW_LOCK_KEY_PREFIX  # noqa: PLC0415

        # Clean up any leftover key from a previous run
        client = await get_redis_client()
        await client.delete(f"{REVIEW_LOCK_KEY_PREFIX}{_TEST_ID}")

        before = await is_already_reviewed(_TEST_ID)
        await mark_as_reviewed(_TEST_ID)
        after = await is_already_reviewed(_TEST_ID)

        # Clean up
        await client.delete(f"{REVIEW_LOCK_KEY_PREFIX}{_TEST_ID}")

        if not before and after:
            record("dedup:lock_set_and_checked", PASS,
                   "False before mark, True after mark")
        else:
            record("dedup:lock_set_and_checked", FAIL,
                   f"before={before} after={after}")
    except ImportError as exc:
        record("dedup:lock_set_and_checked", SKIP,
               f"import failed (activate venv): {exc}")
    except Exception as exc:
        record("dedup:lock_set_and_checked", FAIL, str(exc))


async def test_dry_run_storage() -> None:
    """save_review_submission -> get_review_submission round-trip."""
    _TEST_ID = "test_submission_phase6_temp"
    try:
        from app.services.review_submission_store import (  # noqa: PLC0415
            get_review_submission, save_review_submission,
        )
        from app.services.redis_service import get_redis_client  # noqa: PLC0415
        from app.core.constants import REVIEW_SUBMISSION_KEY_PREFIX  # noqa: PLC0415
        from app.services.github_review_builder import build_review_submission  # noqa: PLC0415

        finding = _make_finding()
        result = _make_result(findings=[finding], high_count=1)
        submission = build_review_submission(result, {**_GRAPH_STATE, "delivery_id": _TEST_ID})

        await save_review_submission(_TEST_ID, submission)
        loaded = await get_review_submission(_TEST_ID)

        # Clean up
        client = await get_redis_client()
        await client.delete(f"{REVIEW_SUBMISSION_KEY_PREFIX}{_TEST_ID}")

        if loaded is None:
            record("dry_run:storage_roundtrip", FAIL, "get returned None after save")
            return

        checks = [
            loaded.owner == submission.owner,
            loaded.repo == submission.repo,
            loaded.pr_number == submission.pr_number,
            loaded.event == submission.event,
            loaded.commit_id == submission.commit_id,
            len(loaded.comments) == len(submission.comments),
        ]
        if all(checks):
            record("dry_run:storage_roundtrip", PASS,
                   f"event={loaded.event} inline_comments={len(loaded.comments)}")
        else:
            record("dry_run:storage_roundtrip", FAIL,
                   f"field mismatch: loaded={loaded.model_dump()}")
    except ImportError as exc:
        record("dry_run:storage_roundtrip", SKIP,
               f"import failed (activate venv): {exc}")
    except Exception as exc:
        record("dry_run:storage_roundtrip", FAIL, str(exc))


# ── Main ───────────────────────────────────────────────────────────────────────

async def run_all() -> None:
    print()
    print("  Phase 6 — GitHub Review Builder Tests")
    print("  " + "=" * 45)

    print()
    print("  [Verdict mapping]")
    print()
    test_verdict_request_changes_high()
    test_verdict_request_changes_critical()
    test_verdict_comment_medium_only()
    test_verdict_approve_no_findings()

    print()
    print("  [Summary body format]")
    print()
    test_summary_body_format()

    print()
    print("  [Inline comment generation]")
    print()
    test_inline_comment_eligible()
    test_inline_comment_no_line()
    test_inline_comment_low_confidence()
    test_inline_comment_body_format()
    test_missing_graph_state_field()

    print()
    print("  [Runtime tests — require Redis]")
    print()
    if not await _redis_ping():
        record("dedup:lock_set_and_checked", SKIP, "Redis not reachable")
        record("dry_run:storage_roundtrip", SKIP, "Redis not reachable")
    else:
        await test_dedup_lock()
        await test_dry_run_storage()


def main() -> None:
    asyncio.run(run_all())

    print()
    passed  = sum(1 for _, s, _ in _results if s == PASS)
    failed  = sum(1 for _, s, _ in _results if s == FAIL)
    skipped = sum(1 for _, s, _ in _results if s == SKIP)
    total   = len(_results)

    print(f"  Results: {passed} passed, {failed} failed, {skipped} skipped / {total} total")
    print()

    if failed:
        print("  Failed tests:")
        for name, status, detail in _results:
            if status == FAIL:
                print(f"    FAIL  {name}" + (f" — {detail}" if detail else ""))
        print()
        sys.exit(1)
    else:
        print("  All tests passed.")
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()
