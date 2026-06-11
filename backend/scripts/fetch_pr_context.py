#!/usr/bin/env python3
"""
CLI helper — fetch and display a PRContext for a stored webhook delivery.

Must be run from the backend/ directory so that app.* imports resolve
and backend/.env is picked up by pydantic-settings:

    cd backend
    python scripts/fetch_pr_context.py <delivery_id>
    python scripts/fetch_pr_context.py <delivery_id> --verbose

Exit codes
----------
0  Success
1  Delivery not found / missing installation ID / bad arguments
2  GitHub API / auth error
3  Unexpected error
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Ensure `app` package is importable when the script is run from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.exceptions import (  # noqa: E402
    DeliveryNotFoundError,
    GitHubAPIError,
    GitHubAuthError,
    MissingInstallationError,
)
from app.services.pr_fetcher import build_pr_context_from_delivery  # noqa: E402


def _separator(char: str = "-", width: int = 60) -> str:
    return char * width


async def run(delivery_id: str, verbose: bool) -> int:
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
        print(f"UNEXPECTED ERROR: {exc}", file=sys.stderr)
        return 3

    m = ctx.metadata

    print(_separator("="))
    print(f"  PR Context  —  delivery: {ctx.delivery_id}")
    print(_separator("="))
    print(f"  Repository : {m.repository_full_name}")
    print(f"  PR Number  : #{m.pr_number}")
    print(f"  Title      : {m.title}")
    print(f"  Author     : {m.author}")
    print(f"  Action     : {ctx.event_action}")
    print(f"  Base       : {m.base_branch}  ({m.base_sha[:7]})")
    print(f"  Head       : {m.head_branch}  ({m.head_sha[:7]})")
    print(f"  URL        : {m.html_url}")
    print(_separator())
    print(f"  Files      : {ctx.total_files}")
    print(f"  Additions  : +{ctx.total_additions}")
    print(f"  Deletions  : -{ctx.total_deletions}")
    print(_separator())
    print("  Changed files:")
    print()

    for f in ctx.changed_files:
        binary_tag = "  [binary]" if f.is_binary else ""
        print(f"    [{f.status:<10}]  +{f.additions:<4} -{f.deletions:<4}  {f.filename}{binary_tag}")

        if verbose and f.patch:
            # Indent each patch line for readability
            for line in f.patch.splitlines():
                print(f"              {line}")
            print()

    print()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch PR context for a stored webhook delivery ID."
    )
    parser.add_argument("delivery_id", help="X-GitHub-Delivery value from the webhook")
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print file patches in addition to summary",
    )
    args = parser.parse_args()

    exit_code = asyncio.run(run(args.delivery_id, args.verbose))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
