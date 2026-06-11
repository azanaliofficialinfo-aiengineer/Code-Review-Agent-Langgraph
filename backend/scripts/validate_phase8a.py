"""
Phase 8A backend validation script.

Checks via source inspection (no DB required).

Usage:
    python scripts/validate_phase8a.py
"""
import re
import sys
from pathlib import Path

GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
RESET  = "\033[0m"

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
_results: list[tuple[str, str, str]] = []
_ROOT = Path(__file__).resolve().parent.parent  # backend/


def _read(rel: str) -> str:
    p = _ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _exists(rel: str) -> bool:
    return (_ROOT / rel).exists()


def record(name: str, status: str, detail: str = "") -> None:
    _results.append((name, status, detail))
    icon = (
        f"{GREEN}[PASS]{RESET}" if status == PASS
        else f"{YELLOW}[SKIP]{RESET}" if status == SKIP
        else f"{RED}[FAIL]{RESET}"
    )
    print(f"  {icon}  {name}" + (f" -- {detail}" if detail else ""))


def check_contains(name: str, rel: str, pattern: str, flags: int = 0) -> None:
    text = _read(rel)
    if not text:
        record(name, FAIL, f"{rel} not found")
        return
    record(name, PASS if re.search(pattern, text, flags) else FAIL,
           "" if re.search(pattern, text, flags) else f"pattern not found: {pattern!r}")


def check_file(name: str, rel: str) -> None:
    record(name, PASS if _exists(rel) else FAIL,
           "" if _exists(rel) else f"missing: {rel}")


print("\n-- Part A: analytics.py exists and has all endpoints --")
check_file("analytics.py exists", "app/api/analytics.py")
for path, pattern in [
    ("GET /analytics/overview",              r'@router\.get.*overview'),
    ("GET /analytics/reviews-per-day",       r'@router\.get.*reviews-per-day'),
    ("GET /analytics/severity-distribution", r'@router\.get.*severity-distribution'),
    ("GET /analytics/verdict-distribution",  r'@router\.get.*verdict-distribution'),
    ("GET /analytics/risk-trend",            r'@router\.get.*risk-trend'),
]:
    check_contains(path, "app/api/analytics.py", pattern)

print("\n-- Analytics: query quality --")
check_contains("Uses async SQLAlchemy session",   "app/api/analytics.py", r"AsyncSession")
check_contains("No Redis imports in analytics",   "app/api/analytics.py", r"redis", re.IGNORECASE)
# redis check is inverted
text = _read("app/api/analytics.py")
record(
    "No Redis imports in analytics",
    PASS if not re.search(r"from app\.services\.redis", text) else FAIL,
)
_results.pop(-2)  # remove the duplicate

check_contains("Uses func.count aggregate",    "app/api/analytics.py", r"func\.count")
check_contains("Uses func.avg aggregate",      "app/api/analytics.py", r"func\.avg")
check_contains("Date filling for time series", "app/api/analytics.py", r"timedelta")
check_contains("Auth dependency applied",      "app/api/analytics.py", r"require_api_auth")
check_contains("Response schemas (Pydantic)",  "app/api/analytics.py", r"class.*BaseModel")
check_contains("days param with validation",   "app/api/analytics.py", r"Query\(\d+.*ge=1.*le=90")

print("\n-- main.py: router registered --")
check_contains("analytics_router imported", "app/main.py", r"analytics_router")
check_contains("analytics_router included", "app/main.py", r"include_router\(analytics_router")

print("\n-- Existing Phase 7.5 contracts intact --")
check_file("auth.py still exists",              "app/core/auth.py")
check_file("persistence_service.py intact",     "app/services/persistence_service.py")
check_file("validate_phase75.py intact",        "scripts/validate_phase75.py")

print("\n" + "=" * 60)
passed  = sum(1 for _, s, _ in _results if s == PASS)
failed  = sum(1 for _, s, _ in _results if s == FAIL)
skipped = sum(1 for _, s, _ in _results if s == SKIP)
print(f"  Phase 8A backend: {passed} PASS  {failed} FAIL  {skipped} SKIP")
print("=" * 60)

sys.exit(1 if failed else 0)
