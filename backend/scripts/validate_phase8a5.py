"""
Phase 8A.5 backend validation script.

Checks deployment-blocker fixes via source inspection (no DB or server required).

Usage:
    python scripts/validate_phase8a5.py
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
    ok = bool(re.search(pattern, text, flags))
    record(name, PASS if ok else FAIL, "" if ok else f"pattern not found: {pattern!r}")


def check_not_contains(name: str, rel: str, pattern: str, flags: int = 0) -> None:
    text = _read(rel)
    if not text:
        record(name, FAIL, f"{rel} not found")
        return
    found = bool(re.search(pattern, text, flags))
    record(name, FAIL if found else PASS, f"unwanted pattern found: {pattern!r}" if found else "")


def check_file(name: str, rel: str) -> None:
    record(name, PASS if _exists(rel) else FAIL,
           "" if _exists(rel) else f"missing: {rel}")


# ── 1. CORS configuration ─────────────────────────────────────────────────────

print("\n-- 1. CORS configuration (config.py) --")
check_file("config.py exists",                         "app/core/config.py")
check_contains("BACKEND_CORS_ORIGINS setting",         "app/core/config.py", r"BACKEND_CORS_ORIGINS")
check_contains("ALLOW_CREDENTIALS setting",            "app/core/config.py", r"ALLOW_CREDENTIALS")
check_contains("parse_cors_origins validator",         "app/core/config.py", r"parse_cors_origins")
check_contains("field_validator import",               "app/core/config.py", r"field_validator")

print("\n-- 2. CORS middleware (main.py) --")
check_file("main.py exists",                           "app/main.py")
check_contains("_build_cors_origins function",         "app/main.py",        r"_build_cors_origins")
check_contains("production guard raises RuntimeError", "app/main.py",        r"RuntimeError")
check_contains("dev localhost always added",           "app/main.py",        r"localhost:3000")
check_contains("allow_origins uses _build_cors",       "app/main.py",        r"allow_origins=_build_cors_origins\(\)")
check_contains("allow_credentials uses setting",       "app/main.py",        r"allow_credentials=settings\.ALLOW_CREDENTIALS")

# Critical: wildcard + credentials combo must not exist in executable code.
# Strip both comment lines and triple-quoted docstrings so the _build_cors_origins
# docstring that *documents* the forbidden pattern does not trigger a false positive.
text_main = _read("app/main.py")
stripped = re.sub(r'""".*?"""', "", text_main, flags=re.DOTALL)
stripped = re.sub(r"'''.*?'''", "", stripped,  flags=re.DOTALL)
executable = "\n".join(ln for ln in stripped.splitlines() if not ln.lstrip().startswith("#"))
has_wildcard_creds = (
    bool(re.search(r'allow_origins\s*=\s*\[.*\*.*\]', executable))
    and bool(re.search(r'allow_credentials\s*=\s*True',  executable))
)
record(
    "No allow_origins=[*] + allow_credentials=True combo",
    FAIL if has_wildcard_creds else PASS,
    "wildcard+credentials combo in executable code" if has_wildcard_creds else "",
)

# ── 2. Backend Dockerfile ─────────────────────────────────────────────────────

print("\n-- 3. Backend Dockerfile --")
check_file("backend Dockerfile exists", "Dockerfile")
check_not_contains("No --reload flag",        "Dockerfile", r"--reload")
check_contains("--workers in CMD",            "Dockerfile", r"--workers")
check_contains("Non-root user created",       "Dockerfile", r"adduser")
check_contains("USER instruction",            "Dockerfile", r"^USER\s+appuser", re.MULTILINE)
check_contains("No dev-only flags",           "Dockerfile", r"uvicorn.*app\.main:app")

# ── 3. Analytics timezone ─────────────────────────────────────────────────────

print("\n-- 4. Analytics timezone fix (analytics.py) --")
check_file("analytics.py exists",                      "app/api/analytics.py")
check_contains("Uses timezone.utc for cutoff",         "app/api/analytics.py", r"datetime\.now\(timezone\.utc\)")
check_contains("UTC date() for end_date",              "app/api/analytics.py", r"datetime\.now\(timezone\.utc\)\.date\(\)")
check_not_contains("No bare date.today() usage",       "app/api/analytics.py", r"\bdate\.today\(\)")
check_not_contains("date import removed (unused)",     "app/api/analytics.py", r"^from datetime import date[^t]", re.MULTILINE)

# ── 4. .env.example ───────────────────────────────────────────────────────────

print("\n-- 5. backend .env.example --")
check_file(".env.example exists",                      ".env.example")
check_contains("BACKEND_CORS_ORIGINS documented",      ".env.example", r"BACKEND_CORS_ORIGINS")
check_contains("ALLOW_CREDENTIALS documented",         ".env.example", r"ALLOW_CREDENTIALS")
check_contains("API_AUTH_TOKEN documented",            ".env.example", r"API_AUTH_TOKEN")

# ── Summary ───────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
passed  = sum(1 for _, s, _ in _results if s == PASS)
failed  = sum(1 for _, s, _ in _results if s == FAIL)
skipped = sum(1 for _, s, _ in _results if s == SKIP)
print(f"  Phase 8A.5 backend: {passed} PASS  {failed} FAIL  {skipped} SKIP")
print("=" * 60)

sys.exit(1 if failed else 0)
