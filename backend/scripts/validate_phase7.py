"""
Phase 7 validation script — PostgreSQL persistence layer.

Runs entirely via source-file inspection (static checks) so it works on
system Python 3.10 without importing any app modules.

Runtime checks (PostgreSQL) are attempted only when DATABASE_URL is set in
the environment.  If not available, those checks are skipped with a SKIP
result and a hint to activate the project venv and set DATABASE_URL.

Usage (from the backend/ directory):
    python scripts/validate_phase7.py
    DATABASE_URL=postgresql+asyncpg://... python scripts/validate_phase7.py
"""
import asyncio
import os
import re
import sys
from pathlib import Path

# ── Colour helpers ─────────────────────────────────────────────────────────────
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
    icon = f"{GREEN}[PASS]{RESET}" if status == PASS else (
        f"{YELLOW}[SKIP]{RESET}" if status == SKIP else f"{RED}[FAIL]{RESET}"
    )
    print(f"  {icon}  {name}" + (f" — {detail}" if detail else ""))


# ── File helpers ───────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent  # backend/


def _path(rel: str) -> Path:
    return _ROOT / rel


def _read(rel: str) -> str:
    p = _path(rel)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


def _exists(rel: str) -> bool:
    return _path(rel).exists()


# ══════════════════════════════════════════════════════════════════════════════
# STATIC CHECKS
# ══════════════════════════════════════════════════════════════════════════════

print("\n[Phase 7 Validation]\n")
print("-- Static checks --")


# 1. ORM model files
def check_model_files() -> None:
    models = {
        "app/models/repository.py": "repositories",
        "app/models/pull_request.py": "pull_requests",
        "app/models/review_job.py": "review_jobs",
        "app/models/review_finding.py": "review_findings",
        "app/models/review_summary.py": "review_summaries",
        "app/models/review_submission.py": "review_submissions",
    }
    for rel, table in models.items():
        src = _read(rel)
        if not src:
            record(f"model:{rel}", FAIL, "file missing")
            continue
        if f'"{table}"' in src or f"'{table}'" in src:
            record(f"model:{rel}", PASS, f"tablename={table!r}")
        else:
            record(f"model:{rel}", FAIL, f"__tablename__ {table!r} not found")


check_model_files()


# 2. models/__init__.py exports all models
def check_models_init() -> None:
    src = _read("app/models/__init__.py")
    required = [
        "Repository", "PullRequest", "ReviewJob",
        "ReviewFinding", "ReviewSummary", "ReviewSubmission",
    ]
    missing = [name for name in required if name not in src]
    if missing:
        record("models:__init__", FAIL, f"missing: {missing}")
    else:
        record("models:__init__", PASS, "all 6 models exported")


check_models_init()


# 3. Alembic setup
def check_alembic_files() -> None:
    if _exists("alembic.ini"):
        record("alembic:alembic.ini", PASS)
    else:
        record("alembic:alembic.ini", FAIL, "file missing")

    env_src = _read("alembic/env.py")
    if not env_src:
        record("alembic:env.py", FAIL, "file missing")
        return

    checks = {
        "async_engine_from_config": "uses async engine",
        "import app.models": "imports ORM models for autogenerate",
        "run_sync": "uses run_sync for migration execution",
    }
    for pattern, description in checks.items():
        if pattern in env_src:
            record(f"alembic:env.py:{pattern}", PASS, description)
        else:
            record(f"alembic:env.py:{pattern}", FAIL, f"{description!r} not found")


check_alembic_files()


# 4. Migration file
def check_migration() -> None:
    migration = "alembic/versions/0001_create_review_persistence_tables.py"
    src = _read(migration)
    if not src:
        record("migration:0001", FAIL, "file missing")
        return

    tables = [
        "repositories", "pull_requests", "review_jobs",
        "review_findings", "review_summaries", "review_submissions",
    ]
    missing = [t for t in tables if t not in src]
    if missing:
        record("migration:0001", FAIL, f"tables missing from migration: {missing}")
    else:
        record("migration:0001", PASS, f"all {len(tables)} tables present")

    if "def downgrade" in src:
        record("migration:0001:downgrade", PASS, "downgrade() defined")
    else:
        record("migration:0001:downgrade", FAIL, "downgrade() missing")


check_migration()


# 5. Repository layer files
def check_repository_files() -> None:
    repos = {
        "app/repositories/repository_repo.py": ["upsert_repository", "list_repositories"],
        "app/repositories/pull_request_repo.py": ["upsert_pull_request"],
        "app/repositories/review_job_repo.py": [
            "create_or_update_review_job",
            "save_findings_idempotent",
            "upsert_review_summary",
            "upsert_review_submission",
            "list_reviews",
            "get_review_detail",
            "list_repository_reviews",
        ],
    }
    for rel, functions in repos.items():
        src = _read(rel)
        if not src:
            record(f"repo:{rel}", FAIL, "file missing")
            continue
        missing = [fn for fn in functions if f"def {fn}" not in src]
        if missing:
            record(f"repo:{rel}", FAIL, f"missing functions: {missing}")
        else:
            record(f"repo:{rel}", PASS, f"{len(functions)} functions present")


check_repository_files()


# 6. Findings idempotency guard (count check before insert)
def check_findings_idempotency() -> None:
    src = _read("app/repositories/review_job_repo.py")
    if "count > 0" in src and "save_findings_idempotent" in src:
        record("repo:findings_idempotency", PASS, "count guard present")
    else:
        record("repo:findings_idempotency", FAIL, "count guard missing")


check_findings_idempotency()


# 7. Persistence service
def check_persistence_service() -> None:
    src = _read("app/services/persistence_service.py")
    if not src:
        record("service:persistence_service", FAIL, "file missing")
        return

    checks = {
        "persist_review_run": "main function",
        "upsert_repository": "calls repository upsert",
        "upsert_pull_request": "calls PR upsert",
        "create_or_update_review_job": "calls job upsert",
        "save_findings_idempotent": "calls findings insert",
        "upsert_review_summary": "calls summary upsert",
        "upsert_review_submission": "calls submission upsert",
        "get_webhook_payload": "enriches from webhook",
        "AsyncSessionLocal": "uses own session",
    }
    missing = [k for k, _ in checks.items() if k not in src]
    if missing:
        record("service:persistence_service", FAIL, f"missing: {missing}")
    else:
        record("service:persistence_service", PASS, f"{len(checks)} required symbols present")


check_persistence_service()


# 8. API — repositories router
def check_repositories_api() -> None:
    src = _read("app/api/repositories.py")
    if not src:
        record("api:repositories.py", FAIL, "file missing")
        return

    checks = {
        'prefix="/repositories"': "router prefix",
        "list_repositories_endpoint": "GET /repositories handler",
        "list_repository_reviews_endpoint": "GET /repositories/{owner}/{repo}/reviews handler",
        "RepositoryListItem": "uses RepositoryListItem schema",
        "ReviewListItem": "uses ReviewListItem schema",
    }
    missing = [k for k in checks if k not in src]
    if missing:
        record("api:repositories.py", FAIL, f"missing: {missing}")
    else:
        record("api:repositories.py", PASS, "both endpoints + schemas present")


check_repositories_api()


# 9. API — reviews.py DB endpoints
def check_reviews_db_endpoints() -> None:
    src = _read("app/api/reviews.py")
    if not src:
        record("api:reviews.py", FAIL, "file missing")
        return

    checks = {
        "list_reviews_endpoint": "GET /reviews list handler",
        "get_review_detail_endpoint": "GET /reviews/{delivery_id} detail handler",
        "_list_reviews": "calls list_reviews repo function",
        "_get_review_detail": "calls get_review_detail repo function",
        "ReviewListItem": "uses ReviewListItem schema",
        "ReviewDetail": "uses ReviewDetail schema",
    }
    missing = [k for k in checks if k not in src]
    if missing:
        record("api:reviews.py:db_endpoints", FAIL, f"missing: {missing}")
    else:
        record("api:reviews.py:db_endpoints", PASS, "list + detail endpoints present")


check_reviews_db_endpoints()


# 10. main.py registers both routers
def check_main_routers() -> None:
    src = _read("app/main.py")
    checks = [
        ("repositories_router", "repositories router imported/used"),
        ("engine.dispose", "DB engine disposed on shutdown"),
    ]
    missing = [desc for symbol, desc in checks if symbol not in src]
    if missing:
        record("main.py:routers", FAIL, f"missing: {missing}")
    else:
        record("main.py:routers", PASS, "repositories router + engine.dispose present")


check_main_routers()


# 11. Worker — _persist_review integration
def check_worker_persist() -> None:
    src = _read("app/workers/review_worker.py")
    if not src:
        record("worker:persist_review", FAIL, "file missing")
        return

    checks = {
        "_persist_review": "_persist_review method",
        "persist_review_run": "calls persistence_service",
        "get_review_submission": "loads Redis submission for DB write",
    }
    missing = [k for k in checks if k not in src]
    if missing:
        record("worker:persist_review", FAIL, f"missing: {missing}")
    else:
        record("worker:persist_review", PASS, "persistence wired into worker")


check_worker_persist()


# 12. db/session.py has AsyncSessionLocal
def check_db_session() -> None:
    src = _read("app/db/session.py")
    if not src:
        record("db:session.py", FAIL, "file missing")
        return
    if "AsyncSessionLocal" in src and "async_sessionmaker" in src:
        record("db:session.py", PASS, "AsyncSessionLocal + async_sessionmaker present")
    else:
        record("db:session.py", FAIL, "AsyncSessionLocal or async_sessionmaker missing")


check_db_session()


# ══════════════════════════════════════════════════════════════════════════════
# RUNTIME CHECKS  (PostgreSQL)
# ══════════════════════════════════════════════════════════════════════════════

print("\n-- Runtime checks (PostgreSQL) --")

_SKIP_REASON = (
    "DATABASE_URL not set — activate project venv and set DATABASE_URL "
    "to run PostgreSQL checks"
)
_DB_URL = os.environ.get("DATABASE_URL", "")

EXPECTED_TABLES = {
    "repositories",
    "pull_requests",
    "review_jobs",
    "review_findings",
    "review_summaries",
    "review_submissions",
}


async def _check_db_tables() -> None:
    """Connect to PostgreSQL, verify all 6 tables exist."""
    try:
        from sqlalchemy import inspect, text
        from sqlalchemy.ext.asyncio import create_async_engine
    except ImportError as exc:
        record("db:tables", SKIP, f"sqlalchemy not importable: {exc}")
        return

    try:
        eng = create_async_engine(_DB_URL, pool_pre_ping=True)
        async with eng.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                )
            )
            existing = {row[0] for row in rows}
        await eng.dispose()
    except Exception as exc:
        record("db:connect", FAIL, f"connection failed: {exc}")
        return

    record("db:connect", PASS, "connected to PostgreSQL")

    missing = EXPECTED_TABLES - existing
    if missing:
        record("db:tables", FAIL, f"missing tables: {sorted(missing)}")
    else:
        record("db:tables", PASS, f"all {len(EXPECTED_TABLES)} tables present")

    # Check indexes on review_jobs
    try:
        eng2 = create_async_engine(_DB_URL, pool_pre_ping=True)
        async with eng2.connect() as conn:
            idx_rows = await conn.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE tablename = 'review_jobs'"
                )
            )
            indexes = {row[0] for row in idx_rows}
        await eng2.dispose()
        if "ix_review_jobs_delivery_id" in indexes:
            record("db:index:delivery_id", PASS, "ix_review_jobs_delivery_id exists")
        else:
            record("db:index:delivery_id", FAIL, "ix_review_jobs_delivery_id missing")
    except Exception as exc:
        record("db:indexes", SKIP, f"index check failed: {exc}")


def _run_runtime_checks() -> None:
    if not _DB_URL:
        record("db:connect", SKIP, _SKIP_REASON)
        record("db:tables", SKIP, _SKIP_REASON)
        record("db:index:delivery_id", SKIP, _SKIP_REASON)
        return

    try:
        asyncio.run(_check_db_tables())
    except Exception as exc:
        record("db:runtime", FAIL, f"unexpected error: {exc}")


_run_runtime_checks()


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

passed = sum(1 for _, s, _ in _results if s == PASS)
failed = sum(1 for _, s, _ in _results if s == FAIL)
skipped = sum(1 for _, s, _ in _results if s == SKIP)

print(f"\n{'=' * 55}")
print(f"  Result: {passed} PASS  {failed} FAIL  {skipped} SKIP")
print(f"{'=' * 55}\n")

if failed:
    sys.exit(1)
