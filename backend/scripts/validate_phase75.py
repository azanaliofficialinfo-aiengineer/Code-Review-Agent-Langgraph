"""
Phase 7.5 validation script — persistence + API hardening sprint.

Runs entirely via source-file inspection (static checks) so it works on
system Python 3.10 without importing any app modules.

Runtime checks (PostgreSQL) are attempted only when DATABASE_URL is set in
the environment.  If not available, those checks are SKIP.

Usage (from the backend/ directory):
    python scripts/validate_phase75.py
    DATABASE_URL=postgresql+asyncpg://... python scripts/validate_phase75.py
"""
import asyncio
import os
import re
import sys
from pathlib import Path

# -- Colour helpers ------------------------------------------------------------─
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
RESET  = "\033[0m"

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

_results: list[tuple[str, str, str]] = []


def record(name: str, status: str, detail: str = "") -> None:
    _results.append((name, status, detail))
    icon = (
        f"{GREEN}[PASS]{RESET}" if status == PASS
        else f"{YELLOW}[SKIP]{RESET}" if status == SKIP
        else f"{RED}[FAIL]{RESET}"
    )
    print(f"  {icon}  {name}" + (f" — {detail}" if detail else ""))


# -- File helpers --------------------------------------------------------------─
_ROOT = Path(__file__).resolve().parent.parent  # backend/


def _path(rel: str) -> Path:
    return _ROOT / rel


def _read(rel: str) -> str:
    p = _path(rel)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def _exists(rel: str) -> bool:
    return _path(rel).exists()


def check_contains(name: str, rel: str, pattern: str, flags: int = 0) -> None:
    text = _read(rel)
    if not text:
        record(name, FAIL, f"{rel} not found")
        return
    if re.search(pattern, text, flags):
        record(name, PASS)
    else:
        record(name, FAIL, f"pattern not found in {rel}: {pattern!r}")


def check_not_contains(name: str, rel: str, pattern: str, flags: int = 0) -> None:
    text = _read(rel)
    if not text:
        record(name, FAIL, f"{rel} not found")
        return
    if re.search(pattern, text, flags):
        record(name, FAIL, f"pattern still present in {rel}: {pattern!r}")
    else:
        record(name, PASS)


def check_file_exists(name: str, rel: str) -> None:
    if _exists(rel):
        record(name, PASS)
    else:
        record(name, FAIL, f"missing: {rel}")


# ==============================================================================
# Section 1 — Fix 1: dry_run no longer hardcoded
# ==============================================================================
print("\n-- Fix 1: dry_run / submitted_to_github no longer hardcoded --")

check_not_contains(
    "persistence_service: dry_run=True is gone",
    "app/services/persistence_service.py",
    r"dry_run\s*=\s*True\s*,\s*$",
    re.MULTILINE,
)
check_not_contains(
    "persistence_service: submitted_to_github=False hardcode is gone",
    "app/services/persistence_service.py",
    r"submitted_to_github\s*=\s*False\s*,\s*$",
    re.MULTILINE,
)
check_contains(
    "persistence_service: dry_run accepted as keyword param",
    "app/services/persistence_service.py",
    r"dry_run\s*:\s*bool\s*=\s*True",
)
check_contains(
    "persistence_service: submitted_to_github accepted as keyword param",
    "app/services/persistence_service.py",
    r"submitted_to_github\s*:\s*bool\s*=\s*False",
)
check_contains(
    "persistence_service: github_review_id accepted as keyword param",
    "app/services/persistence_service.py",
    r"github_review_id\s*:\s*int\s*\|\s*None\s*=\s*None",
)

# ==============================================================================
# Section 2 — Fix 2: installation_id=0 prevention
# ==============================================================================
print("\n-- Fix 2: installation_id resolution --")

check_not_contains(
    "persistence_service: no more 'if installation_id_raw else 0'",
    "app/services/persistence_service.py",
    r"installation_id_raw\s*\)\s*if\s+installation_id_raw\s+else\s+0",
)
check_contains(
    "persistence_service: _resolve_installation_id helper exists",
    "app/services/persistence_service.py",
    r"async def _resolve_installation_id",
)
check_contains(
    "persistence_service: raises ValueError on zero installation_id",
    "app/services/persistence_service.py",
    r"raise ValueError",
)

# ==============================================================================
# Section 3 — Fix 3: duplicate index cleanup
# ==============================================================================
print("\n-- Fix 3: duplicate index cleanup --")

check_not_contains(
    "repository model: no duplicate ix_repositories_full_name Index()",
    "app/models/repository.py",
    r'Index\s*\(\s*["\']ix_repositories_full_name',
)
check_not_contains(
    "review_job model: no duplicate ix_review_jobs_delivery_id Index()",
    "app/models/review_job.py",
    r'Index\s*\(\s*["\']ix_review_jobs_delivery_id',
)
check_contains(
    "review_job model: composite ix_review_jobs_repo_created exists",
    "app/models/review_job.py",
    r'ix_review_jobs_repo_created',
)
check_contains(
    "review_job model: composite ix_review_jobs_status_created exists",
    "app/models/review_job.py",
    r'ix_review_jobs_status_created',
)
check_contains(
    "review_finding model: composite ix_review_findings_job_severity exists",
    "app/models/review_finding.py",
    r'ix_review_findings_job_severity',
)
check_file_exists(
    "migration 0002_fix_indexes.py exists",
    "alembic/versions/0002_fix_indexes.py",
)
check_contains(
    "migration 0002: drops ix_repositories_full_name (IF EXISTS)",
    "alembic/versions/0002_fix_indexes.py",
    r"DROP INDEX IF EXISTS ix_repositories_full_name",
)
check_contains(
    "migration 0002: drops ix_review_jobs_delivery_id (IF EXISTS)",
    "alembic/versions/0002_fix_indexes.py",
    r"DROP INDEX IF EXISTS ix_review_jobs_delivery_id",
)

# ==============================================================================
# Section 4 — Fix 4 & 5: pagination wrappers
# ==============================================================================
print("\n-- Fix 4 & 5: pagination wrappers and findings pagination --")

check_contains(
    "db_schemas: PaginatedReviews defined",
    "app/schemas/db_schemas.py",
    r"class PaginatedReviews",
)
check_contains(
    "db_schemas: PaginatedRepositories defined",
    "app/schemas/db_schemas.py",
    r"class PaginatedRepositories",
)
check_contains(
    "db_schemas: PaginatedRepositoryReviews defined",
    "app/schemas/db_schemas.py",
    r"class PaginatedRepositoryReviews",
)
check_contains(
    "db_schemas: PaginatedFindingList defined",
    "app/schemas/db_schemas.py",
    r"class PaginatedFindingList",
)
check_contains(
    "db_schemas: ReviewDetail.findings is PaginatedFindingList",
    "app/schemas/db_schemas.py",
    r"findings\s*:\s*PaginatedFindingList",
)
check_contains(
    "reviews API: list endpoint returns PaginatedReviews",
    "app/api/reviews.py",
    r"response_model\s*=\s*PaginatedReviews",
)
check_contains(
    "repositories API: list endpoint returns PaginatedRepositories",
    "app/api/repositories.py",
    r"response_model\s*=\s*PaginatedRepositories",
)
check_contains(
    "repositories API: repo reviews returns PaginatedRepositoryReviews",
    "app/api/repositories.py",
    r"response_model\s*=\s*PaginatedRepositoryReviews",
)

# ==============================================================================
# Section 5 — Fix 5: N+1 fix in get_review_detail
# ==============================================================================
print("\n-- Fix 5: N+1 fix in get_review_detail --")

check_contains(
    "review_job_repo: get_review_detail accepts findings_limit param",
    "app/repositories/review_job_repo.py",
    r"findings_limit\s*:\s*int\s*\|",
)
check_contains(
    "review_job_repo: get_review_detail accepts findings_offset param",
    "app/repositories/review_job_repo.py",
    r"findings_offset\s*:\s*int\s*=\s*0",
)
check_contains(
    "review_job_repo: uses single JOIN (5-table) in get_review_detail",
    "app/repositories/review_job_repo.py",
    r"ReviewSubmission.*outerjoin|outerjoin.*ReviewSubmission",
    re.DOTALL,
)
check_contains(
    "review_job_repo: count_reviews helper exists",
    "app/repositories/review_job_repo.py",
    r"async def count_reviews",
)
check_contains(
    "review_job_repo: count_repository_reviews helper exists",
    "app/repositories/review_job_repo.py",
    r"async def count_repository_reviews",
)
check_contains(
    "review_job_repo: list_repository_reviews uses single JOIN",
    "app/repositories/review_job_repo.py",
    r"async def list_repository_reviews",
)

# ==============================================================================
# Section 6 — Fix 6: findings pagination query params
# ==============================================================================
print("\n-- Fix 6: findings pagination query params --")

check_contains(
    "reviews API: findings_limit Query param",
    "app/api/reviews.py",
    r"findings_limit.*Query",
)
check_contains(
    "reviews API: findings_offset Query param",
    "app/api/reviews.py",
    r"findings_offset.*Query",
)
check_contains(
    "reviews API: detail builds PaginatedFindingList",
    "app/api/reviews.py",
    r"PaginatedFindingList\s*\(",
)

# ==============================================================================
# Section 7 — Fix 7: bearer-token auth
# ==============================================================================
print("\n-- Fix 7: bearer-token auth --")

check_file_exists(
    "app/core/auth.py exists",
    "app/core/auth.py",
)
check_contains(
    "auth.py: require_api_auth function defined",
    "app/core/auth.py",
    r"async def require_api_auth",
)
check_contains(
    "auth.py: uses secrets.compare_digest (timing-safe)",
    "app/core/auth.py",
    r"secrets\.compare_digest",
)
check_contains(
    "auth.py: WWW-Authenticate Bearer header on 401",
    "app/core/auth.py",
    r"WWW-Authenticate.*Bearer",
)
check_contains(
    "config.py: API_AUTH_ENABLED setting",
    "app/core/config.py",
    r"API_AUTH_ENABLED",
)
check_contains(
    "config.py: API_AUTH_TOKEN setting",
    "app/core/config.py",
    r"API_AUTH_TOKEN",
)
check_contains(
    "reviews API: auth on list endpoint",
    "app/api/reviews.py",
    r"require_api_auth",
)
check_contains(
    "repositories API: auth on list endpoint",
    "app/api/repositories.py",
    r"require_api_auth",
)
check_contains(
    "debug API: auth on router",
    "app/api/debug.py",
    r"require_api_auth",
)

# ==============================================================================
# Section 8 — Fix 8: status filter validation
# ==============================================================================
print("\n-- Fix 8: status filter validation --")

check_contains(
    "reviews API: _VALID_STATUSES frozenset defined",
    "app/api/reviews.py",
    r"_VALID_STATUSES\s*=\s*frozenset",
)
check_contains(
    "reviews API: raises 400 on invalid status",
    "app/api/reviews.py",
    r"status_code\s*=\s*400",
)
check_contains(
    "reviews API: validates status not in _VALID_STATUSES",
    "app/api/reviews.py",
    r"status\s+not\s+in\s+_VALID_STATUSES",
)

# ==============================================================================
# Section 9 — Fix 9: Redis->Postgres fallback
# ==============================================================================
print("\n-- Fix 9: Redis->Postgres fallback in /status and /result --")

check_contains(
    "reviews API: /status endpoint has DB session param",
    "app/api/reviews.py",
    r"async def get_review_status.*session.*AsyncSession",
    re.DOTALL,
)
check_contains(
    "reviews API: /status falls back to DB on Redis miss",
    "app/api/reviews.py",
    r"_get_job\s*\(",
)
check_contains(
    "reviews API: /status adds source=database on fallback",
    "app/api/reviews.py",
    r'"source".*"database"',
)
check_contains(
    "reviews API: /result falls back to DB (_get_review_detail)",
    "app/api/reviews.py",
    r"_get_review_detail\s*\(",
)

# ==============================================================================
# Section 10 — Fix 10: worker threads submission metadata
# ==============================================================================
print("\n-- Fix 10: worker threads submission metadata --")

check_contains(
    "worker: _submit_review returns dict | None",
    "app/workers/review_worker.py",
    r"async def _submit_review.*->.*dict\s*\|",
    re.DOTALL,
)
check_contains(
    "worker: _submit_review returns dry_run metadata",
    "app/workers/review_worker.py",
    r'"dry_run"',
)
check_contains(
    "worker: _submit_review returns submitted_to_github metadata",
    "app/workers/review_worker.py",
    r'"submitted_to_github"',
)
check_contains(
    "worker: _persist_review accepts submission_meta",
    "app/workers/review_worker.py",
    r"submission_meta\s*:\s*dict\s*\|",
)
check_contains(
    "worker: passes dry_run to persist_review_run",
    "app/workers/review_worker.py",
    r"dry_run\s*=\s*meta\.get",
)

# ==============================================================================
# Section 11 — Webhook auth protection NOT added
# ==============================================================================
print("\n-- Constraint: webhook endpoint has NO auth --")

check_not_contains(
    "webhooks router: no require_api_auth dependency",
    "app/api/webhooks.py",
    r"require_api_auth",
)

# ==============================================================================
# Section 12 — repository_repo has count_repositories
# ==============================================================================
print("\n-- Fix: repository_repo count helper --")

check_contains(
    "repository_repo: count_repositories exists",
    "app/repositories/repository_repo.py",
    r"async def count_repositories",
)

# ==============================================================================
# Runtime checks (DB)
# ==============================================================================

DATABASE_URL = os.environ.get("DATABASE_URL", "")


async def _runtime_checks() -> None:
    print("\n-- Runtime checks (PostgreSQL) --")

    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
    except ImportError:
        record("DB import", SKIP, "sqlalchemy not installed — activate venv first")
        return

    engine = create_async_engine(DATABASE_URL, echo=False)
    try:
        async with engine.connect() as conn:
            # Check all 6 tables exist
            for table in (
                "repositories", "pull_requests", "review_jobs",
                "review_findings", "review_summaries", "review_submissions",
            ):
                try:
                    await conn.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
                    record(f"DB table '{table}' exists", PASS)
                except Exception as exc:
                    record(f"DB table '{table}' exists", FAIL, str(exc))

            # Check 0002 migration has run (composite indexes exist)
            for idx in (
                "ix_review_jobs_repo_created",
                "ix_review_jobs_status_created",
                "ix_review_findings_job_severity",
            ):
                try:
                    result = await conn.execute(
                        text(
                            "SELECT 1 FROM pg_indexes "
                            f"WHERE indexname = '{idx}'"
                        )
                    )
                    if result.fetchone():
                        record(f"DB index '{idx}' exists", PASS)
                    else:
                        record(f"DB index '{idx}' exists", FAIL, "run: alembic upgrade head")
                except Exception as exc:
                    record(f"DB index '{idx}' check", FAIL, str(exc))

            # Check duplicate indexes are gone
            for bad_idx in ("ix_repositories_full_name", "ix_review_jobs_delivery_id"):
                try:
                    result = await conn.execute(
                        text(
                            "SELECT 1 FROM pg_indexes "
                            f"WHERE indexname = '{bad_idx}'"
                        )
                    )
                    if result.fetchone():
                        record(f"DB duplicate index '{bad_idx}' removed", FAIL, "run: alembic upgrade head")
                    else:
                        record(f"DB duplicate index '{bad_idx}' removed", PASS)
                except Exception as exc:
                    record(f"DB duplicate index '{bad_idx}' check", FAIL, str(exc))

    except Exception as exc:
        record("DB connection", FAIL, str(exc))
    finally:
        await engine.dispose()


if DATABASE_URL:
    asyncio.run(_runtime_checks())
else:
    print("\n-- Runtime checks (PostgreSQL) --")
    print(f"  {YELLOW}[SKIP]{RESET}  All DB checks — set DATABASE_URL to run")

# ==============================================================================
# Summary
# ==============================================================================
print("\n" + "=" * 60)
passed = sum(1 for _, s, _ in _results if s == PASS)
failed = sum(1 for _, s, _ in _results if s == FAIL)
skipped = sum(1 for _, s, _ in _results if s == SKIP)
print(f"  Phase 7.5 validation: {passed} PASS  {failed} FAIL  {skipped} SKIP")
print("=" * 60)

if failed:
    sys.exit(1)
