#!/usr/bin/env python3
"""
Lightweight unit tests for AI review parsing and scoring logic.

Run from the backend/ directory (no external services required):

    cd backend
    python scripts/test_review_parsing.py

All tests exercise pure-Python logic: JSON extraction, confidence filtering,
score calculation, and should_comment enforcement. No Groq API calls are made.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
os.environ.setdefault("GROQ_API_KEY", "test-key")   # prevent config validation error

from app.schemas.review_result import ReviewFinding, ReviewSummary  # noqa: E402
from app.services.groq_reviewer import (  # noqa: E402
    _build_summary,
    _extract_added_line_numbers,
    _extract_json,
    _parse_findings,
)

PASS = "PASS"
FAIL = "FAIL"
_results: list[tuple[str, str]] = []


def test(name: str, condition: bool) -> None:
    status = PASS if condition else FAIL
    _results.append((name, status))
    icon = "." if condition else "F"
    print(icon, end="", flush=True)


# ── JSON extraction ────────────────────────────────────────────────────────────

def test_json_extraction() -> None:
    # Valid direct JSON
    out = _extract_json('{"findings": []}')
    test("json_direct_empty", out == {"findings": []})

    # Wrapped in markdown fence
    out = _extract_json('```json\n{"findings": [{"title": "test"}]}\n```')
    test("json_markdown_fence", out["findings"][0]["title"] == "test")

    # Bare fence without language tag
    out = _extract_json('```\n{"findings": []}\n```')
    test("json_bare_fence", out == {"findings": []})

    # JSON buried in prose text
    out = _extract_json('Here is my analysis:\n{"findings": [{"severity": "high"}]}\nDone.')
    test("json_buried_in_prose", out["findings"][0]["severity"] == "high")

    # Completely malformed — should return safe fallback
    out = _extract_json("Sorry, I cannot review this code.")
    test("json_malformed_fallback", out == {"findings": []})

    # Empty string
    out = _extract_json("")
    test("json_empty_string", out == {"findings": []})


# ── Line number extraction ─────────────────────────────────────────────────────

def test_line_number_extraction() -> None:
    patch = (
        "@@ -10,5 +10,6 @@\n"
        " context\n"
        "-removed\n"
        "+added_line_11\n"
        " context\n"
        "+added_line_13\n"
        " context\n"
    )
    added = _extract_added_line_numbers(patch)
    test("line_added_11", 11 in added)
    test("line_added_13", 13 in added)
    test("line_removed_not_in_added", 12 not in added)  # removed line

    # Empty patch
    test("line_empty_patch", _extract_added_line_numbers("") == set())

    # Multi-hunk patch
    multi_hunk = (
        "@@ -1,3 +1,4 @@\n"
        " ctx\n"
        "+new_line_2\n"
        " ctx\n"
        " ctx\n"
        "@@ -20,3 +21,4 @@\n"
        " ctx\n"
        "+new_line_22\n"
        " ctx\n"
        " ctx\n"
    )
    added2 = _extract_added_line_numbers(multi_hunk)
    test("line_multi_hunk_first", 2 in added2)
    test("line_multi_hunk_second", 22 in added2)


# ── Finding parsing & confidence filtering ─────────────────────────────────────

def test_finding_parsing() -> None:
    raw = [
        {
            "file_path": "src/auth.py",
            "line": 42,
            "severity": "high",
            "category": "security",
            "title": "SQL injection risk",
            "description": "User input not sanitised",
            "suggestion": "Use parameterised queries",
            "confidence": 0.91,
        },
        {
            # missing several fields — should still parse with defaults
            "severity": "low",
            "category": "style",
            "title": "Long line",
            "description": "Line too long",
            "suggestion": "Wrap it",
            "confidence": 0.40,
        },
        {
            # completely invalid — should be skipped
            "severity": "INVALID_SEVERITY",
            "confidence": "not-a-float",
        },
    ]

    findings = _parse_findings(raw, "src/auth.py", {42})
    test("parse_valid_count", len(findings) == 2)          # third entry is skipped

    f0 = findings[0]
    test("parse_file_path", f0.file_path == "src/auth.py")
    test("parse_line_in_added", f0.line == 42)
    test("parse_severity_high", f0.severity == "high")
    test("parse_confidence", f0.confidence == 0.91)

    # Line not in added_lines → should be nullified
    raw_off = [{**raw[0], "line": 99}]
    off = _parse_findings(raw_off, "src/auth.py", {42})
    test("parse_line_not_in_added_nullified", off[0].line is None)

    # No added_lines set (empty) → keep line as-is
    with_line = _parse_findings([{**raw[0], "line": 55}], "src/auth.py", set())
    test("parse_line_kept_when_no_added_set", with_line[0].line == 55)


# ── should_comment logic ───────────────────────────────────────────────────────

def test_should_comment() -> None:
    def make(severity: str, category: str, confidence: float) -> ReviewFinding:
        return ReviewFinding(
            file_path="f.py", line=1, severity=severity, category=category,
            title="t", description="d", suggestion="s", confidence=confidence,
        )

    # High confidence security high severity → should comment
    test("should_comment_high_security", make("high", "security", 0.90).should_comment is True)

    # High confidence critical → should comment
    test("should_comment_critical", make("critical", "logic_bug", 0.80).should_comment is True)

    # Medium severity but below threshold → should NOT comment
    test("should_comment_low_confidence", make("medium", "logic_bug", 0.50).should_comment is False)

    # Style findings never get commented regardless of severity/confidence
    test("should_comment_style_excluded", make("high", "style", 0.99).should_comment is False)

    # Low severity high confidence → should NOT comment
    test("should_comment_low_severity", make("low", "security", 0.95).should_comment is False)

    # Exactly at threshold → should comment (>= not >)
    from app.core.config import settings
    test("should_comment_at_threshold", make("medium", "logic_bug", settings.AI_MIN_CONFIDENCE).should_comment is True)


# ── Summary and scoring ────────────────────────────────────────────────────────

def test_summary_scoring() -> None:
    def finding(severity: str) -> ReviewFinding:
        return ReviewFinding(
            file_path="f.py", line=1, severity=severity, category="logic_bug",
            title="t", description="d", suggestion="s", confidence=0.9,
        )

    # Empty findings → approve
    s = _build_summary([])
    test("summary_empty_approve", s.verdict == "approve")
    test("summary_empty_score_0", s.severity_score == 0)
    test("summary_empty_risk_low", s.risk_level == "low")

    # Low only → approve
    s = _build_summary([finding("low"), finding("low")])
    test("summary_low_only_approve", s.verdict == "approve")
    test("summary_low_score", s.severity_score == 6)  # 2 × 3

    # Medium only → comment
    s = _build_summary([finding("medium")])
    test("summary_medium_comment", s.verdict == "comment")
    test("summary_medium_score", s.severity_score == 10)

    # High present → request_changes
    s = _build_summary([finding("high")])
    test("summary_high_request_changes", s.verdict == "request_changes")

    # Critical present → request_changes
    s = _build_summary([finding("critical")])
    test("summary_critical_request_changes", s.verdict == "request_changes")

    # Score cap at 100
    many_critical = [finding("critical")] * 10
    s = _build_summary(many_critical)
    test("summary_score_capped_100", s.severity_score == 100)

    # Risk level boundaries
    s_15 = _build_summary([finding("low")] * 5)   # 5×3=15 → low
    test("summary_risk_low_boundary", s_15.risk_level == "low")

    s_20 = _build_summary([finding("medium")] * 2)  # 2×10=20 → medium
    test("summary_risk_medium", s_20.risk_level == "medium")

    s_50 = _build_summary([finding("high")] * 3)   # 3×20=60 → high... wait, 60 is high
    test("summary_risk_high", s_50.risk_level == "high")

    s_crit = _build_summary([finding("critical")] * 3)  # 3×35=105 → capped 100 → critical
    test("summary_risk_critical", s_crit.risk_level == "critical")

    # Counts are correct
    mixed = [finding("critical"), finding("high"), finding("medium"), finding("low")]
    s = _build_summary(mixed)
    test("summary_count_critical", s.critical_count == 1)
    test("summary_count_high", s.high_count == 1)
    test("summary_count_medium", s.medium_count == 1)
    test("summary_count_low", s.low_count == 1)
    test("summary_count_total", s.total_findings == 4)


# ── Run all suites ─────────────────────────────────────────────────────────────

def main() -> None:
    suites = [
        ("JSON extraction",       test_json_extraction),
        ("Line number extraction", test_line_number_extraction),
        ("Finding parsing",        test_finding_parsing),
        ("should_comment logic",   test_should_comment),
        ("Summary scoring",        test_summary_scoring),
    ]

    print()
    for suite_name, suite_fn in suites:
        print(f"  {suite_name:<30} ", end="")
        suite_fn()
        print()

    passed = sum(1 for _, s in _results if s == PASS)
    failed = sum(1 for _, s in _results if s == FAIL)
    total  = len(_results)

    print()
    print(f"  Results: {passed}/{total} passed", end="")
    if failed:
        print(f"  ({failed} FAILED)")
        print()
        print("  Failed tests:")
        for name, status in _results:
            if status == FAIL:
                print(f"    - {name}")
    else:
        print("  — all passed")
    print()

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
