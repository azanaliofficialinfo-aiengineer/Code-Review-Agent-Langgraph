#!/usr/bin/env python3
"""
Run AI code review for a stored webhook delivery and print results.

Must be run from the backend/ directory:

    cd backend
    python scripts/review_pr.py <delivery_id>
    python scripts/review_pr.py <delivery_id> --verbose

Exit codes
----------
0  Success (review completed — may have findings)
1  Delivery not found / payload problem
2  GitHub API / auth error
3  AI provider error
4  Unexpected error
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.exceptions import (  # noqa: E402
    AIProviderConfigError,
    AIReviewError,
    DeliveryNotFoundError,
    GitHubAPIError,
    GitHubAuthError,
    MissingInstallationError,
)
from app.services.ai_provider import get_ai_provider  # noqa: E402
from app.services.pr_fetcher import build_pr_context_from_delivery  # noqa: E402


_SEP_WIDE  = "=" * 64
_SEP_LIGHT = "-" * 64

_SEVERITY_ICON = {
    "critical": "[CRITICAL]",
    "high":     "[HIGH    ]",
    "medium":   "[MEDIUM  ]",
    "low":      "[LOW     ]",
}

_VERDICT_ICON = {
    "request_changes": "REQUEST CHANGES",
    "comment":         "COMMENT",
    "approve":         "APPROVE",
}


async def run(delivery_id: str, verbose: bool) -> int:
    # ── Fetch PR context ───────────────────────────────────────────────────
    try:
        ctx = await build_pr_context_from_delivery(delivery_id)
    except DeliveryNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except MissingInstallationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except (GitHubAuthError, GitHubAPIError) as exc:
        print(f"ERROR (GitHub): {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"UNEXPECTED ERROR fetching PR: {exc}", file=sys.stderr)
        return 4

    # ── Run AI review ──────────────────────────────────────────────────────
    try:
        provider = get_ai_provider()
        result = await provider.review_pr(ctx)
    except AIProviderConfigError as exc:
        print(f"ERROR (AI config): {exc}", file=sys.stderr)
        return 3
    except AIReviewError as exc:
        print(f"ERROR (AI review): {exc}", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"UNEXPECTED ERROR during review: {exc}", file=sys.stderr)
        return 4

    # ── Print results ──────────────────────────────────────────────────────
    m = ctx.metadata
    s = result.summary

    print(_SEP_WIDE)
    print(f"  AI Code Review  —  {m.repository_full_name} #{m.pr_number}")
    print(_SEP_WIDE)
    print(f"  Provider  : {result.provider}")
    print(f"  Model     : {result.model}")
    print(f"  PR Title  : {m.title}")
    print(f"  Author    : {m.author}")
    print(f"  Delivery  : {result.delivery_id}")
    print(_SEP_LIGHT)
    print(f"  Verdict   : {_VERDICT_ICON.get(s.verdict, s.verdict)}")
    print(f"  Risk      : {s.risk_level.upper()}  (score {s.severity_score}/100)")
    print(f"  Findings  : {s.total_findings}  "
          f"(critical={s.critical_count}  high={s.high_count}  "
          f"medium={s.medium_count}  low={s.low_count})")
    print(_SEP_LIGHT)
    print(f"  Summary   : {s.summary_text}")
    print()

    if result.reviewed_files:
        print(f"  Reviewed files ({len(result.reviewed_files)}):")
        for f in result.reviewed_files:
            print(f"    + {f}")
    if result.skipped_files:
        print(f"\n  Skipped files ({len(result.skipped_files)}):")
        for f in result.skipped_files:
            print(f"    - {f}")

    if not result.findings:
        print("\n  No actionable findings.")
    else:
        # Group by file
        by_file: dict[str, list] = {}
        for finding in result.findings:
            by_file.setdefault(finding.file_path, []).append(finding)

        print(f"\n  Findings by file:")
        for filepath, file_findings in by_file.items():
            print(f"\n  {filepath}")
            print(f"  {'~' * min(len(filepath), 56)}")
            for f in file_findings:
                icon = _SEVERITY_ICON.get(f.severity, f"[{f.severity.upper()}]")
                line_ref = f"  line {f.line}" if f.line else "  (line unknown)"
                comment_flag = " [will comment]" if f.should_comment else ""
                print(f"\n    {icon}  {f.title}{comment_flag}")
                print(f"    Category   : {f.category}")
                print(f"    Location   : {line_ref}")
                print(f"    Confidence : {f.confidence:.0%}")
                if verbose:
                    print(f"    Details    : {f.description}")
                    print(f"    Suggestion : {f.suggestion}")

    print()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AI review for a webhook delivery.")
    parser.add_argument("delivery_id", help="X-GitHub-Delivery ID of the stored webhook")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show finding descriptions and suggestions")
    args = parser.parse_args()

    sys.exit(asyncio.run(run(args.delivery_id, args.verbose)))


if __name__ == "__main__":
    main()
