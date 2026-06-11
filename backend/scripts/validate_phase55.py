#!/usr/bin/env python3
"""
Phase 5.5 hardening readiness validation.

Checks every requirement added in Phase 5.5 and prints a PASS / FAIL report.

Static checks use source-file inspection (no module imports) so they run
correctly on any Python version, including the system Python used outside
the project venv.

Runtime checks (Redis ping, heartbeat, result-store roundtrip) require the
project venv with all dependencies installed.  They are skipped gracefully
if imports fail.

Usage
-----
    cd backend
    python scripts/validate_phase55.py                        # core checks
    python scripts/validate_phase55.py --delivery-id <id>    # + graph-state fields
    python scripts/validate_phase55.py --full                 # + result store roundtrip
    python scripts/validate_phase55.py --require-worker      # fail if heartbeat absent

Exit codes: 0 = all checks passed, 1 = one or more FAIL.
"""
import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os  # noqa: E402
os.environ.setdefault("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", "test-key"))

_BASE = Path(__file__).resolve().parent.parent   # backend/

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


def _read(rel: str) -> str:
    return (_BASE / rel).read_text(encoding="utf-8")


# ── Static checks (source-file inspection, no imports) ────────────────────────

def check_config_timeout() -> None:
    src = _read("app/core/config.py")
    match = re.search(r'REVIEW_JOB_TIMEOUT_SECONDS\s*:\s*int\s*=\s*(\d+)', src)
    if match and int(match.group(1)) > 0:
        record("config:REVIEW_JOB_TIMEOUT_SECONDS", PASS, f"default={match.group(1)}s")
    else:
        record("config:REVIEW_JOB_TIMEOUT_SECONDS", FAIL,
               "not found or value <= 0 in config.py")


def check_constants_queue_key() -> None:
    src = _read("app/core/constants.py")
    expected = "github:review_queue"
    if f'"{expected}"' in src or f"'{expected}'" in src:
        record("constants:REVIEW_QUEUE_KEY", PASS, f"'{expected}'")
    else:
        record("constants:REVIEW_QUEUE_KEY", FAIL,
               f"'{expected}' not found in constants.py")


def check_constants_heartbeat_key() -> None:
    src = _read("app/core/constants.py")
    expected = "github:worker:heartbeat"
    if f'"{expected}"' in src or f"'{expected}'" in src:
        record("constants:WORKER_HEARTBEAT_KEY", PASS, f"'{expected}'")
    else:
        record("constants:WORKER_HEARTBEAT_KEY", FAIL,
               f"'{expected}' not found in constants.py")


def check_review_status_literal() -> None:
    src = _read("app/graph/state.py")
    required = ["queued", "fetching_context", "reviewing", "completed", "failed"]
    has_literal = "ReviewStatus" in src and "Literal" in src
    has_all = all(f'"{v}"' in src or f"'{v}'" in src for v in required)
    if has_literal and has_all:
        record("state:ReviewStatus_Literal", PASS, f"all {len(required)} values present")
    else:
        missing = [v for v in required if f'"{v}"' not in src and f"'{v}'" not in src]
        record("state:ReviewStatus_Literal", FAIL,
               f"missing={missing}" if missing else "ReviewStatus or Literal not found")


def check_review_state_uses_status_type() -> None:
    src = _read("app/graph/state.py")
    if re.search(r'status\s*:\s*ReviewStatus', src):
        record("state:ReviewState.status_typed", PASS, "status: ReviewStatus")
    else:
        record("state:ReviewState.status_typed", FAIL,
               "status field is not typed as ReviewStatus")


def check_graph_state_phase6_fields() -> None:
    src = _read("app/services/graph_state_store.py")
    required = ["installation_id", "owner", "repo", "head_sha", "base_sha"]
    missing = [f for f in required if f'"{f}"' not in src and f"'{f}'" not in src]
    if not missing:
        record("graph_state_store:phase6_metadata_fields", PASS,
               f"all {len(required)} fields present")
    else:
        record("graph_state_store:phase6_metadata_fields", FAIL,
               f"missing: {missing}")


def check_mark_graph_state_failed() -> None:
    src = _read("app/services/graph_state_store.py")
    if re.search(r'async def mark_graph_state_failed', src):
        record("graph_state_store:mark_graph_state_failed", PASS,
               "async def present")
    else:
        record("graph_state_store:mark_graph_state_failed", FAIL,
               "async def mark_graph_state_failed not found")


def check_save_state_safe_helper() -> None:
    src = _read("app/graph/review_graph.py")
    if re.search(r'async def _save_state_safe', src):
        record("review_graph:_save_state_safe_helper", PASS)
    else:
        record("review_graph:_save_state_safe_helper", FAIL,
               "_save_state_safe not found in review_graph.py")


def check_finalize_fatal_on_result_failure() -> None:
    src = _read("app/graph/review_graph.py")
    # Verify that finalize_node returns a "failed" update when save_review_result raises
    if re.search(r'status.*failed.*save_review_result|save_review_result.*status.*failed', src, re.DOTALL):
        record("review_graph:finalize_fatal_on_result_failure", PASS,
               "finalize_node transitions to failed on save_review_result error")
    else:
        record("review_graph:finalize_fatal_on_result_failure", FAIL,
               "finalize_node may still return 'completed' when save_review_result fails")


def check_worker_job_timeout() -> None:
    src = _read("app/workers/review_worker.py")
    has_wait_for = "asyncio.wait_for" in src
    has_timeout_setting = "REVIEW_JOB_TIMEOUT_SECONDS" in src
    has_timeout_error = "asyncio.TimeoutError" in src
    if has_wait_for and has_timeout_setting and has_timeout_error:
        record("worker:job_timeout", PASS,
               "asyncio.wait_for + REVIEW_JOB_TIMEOUT_SECONDS + TimeoutError handler")
    else:
        missing = []
        if not has_wait_for:
            missing.append("asyncio.wait_for")
        if not has_timeout_setting:
            missing.append("REVIEW_JOB_TIMEOUT_SECONDS")
        if not has_timeout_error:
            missing.append("asyncio.TimeoutError handler")
        record("worker:job_timeout", FAIL, f"missing: {missing}")


def check_worker_backoff() -> None:
    src = _read("app/workers/review_worker.py")
    has_seq = "_BACKOFF_SEQUENCE" in src
    has_idx = "_backoff_idx" in src
    if has_seq and has_idx:
        match = re.search(r'_BACKOFF_SEQUENCE\s*=\s*(\([^)]+\))', src)
        seq_str = match.group(1) if match else "found"
        record("worker:exponential_backoff", PASS, f"sequence={seq_str}")
    else:
        record("worker:exponential_backoff", FAIL,
               "_BACKOFF_SEQUENCE or _backoff_idx missing from review_worker.py")


def check_worker_heartbeat_loop() -> None:
    src = _read("app/workers/review_worker.py")
    if re.search(r'async def _heartbeat_loop', src):
        record("worker:heartbeat_loop", PASS, "async def _heartbeat_loop present")
    else:
        record("worker:heartbeat_loop", FAIL,
               "async def _heartbeat_loop not found in review_worker.py")


def check_worker_heartbeat_uses_constants() -> None:
    src = _read("app/workers/review_worker.py")
    if "WORKER_HEARTBEAT_KEY" in src and "REVIEW_QUEUE_KEY" in src:
        if re.search(r'from app\.core\.constants import', src):
            record("worker:imports_from_constants", PASS,
                   "REVIEW_QUEUE_KEY and WORKER_HEARTBEAT_KEY imported from constants")
        else:
            record("worker:imports_from_constants", FAIL,
                   "constants used but not imported from app.core.constants")
    else:
        record("worker:imports_from_constants", FAIL,
               "WORKER_HEARTBEAT_KEY or REVIEW_QUEUE_KEY missing from review_worker.py")


def check_queue_key_not_duplicated() -> None:
    worker_src = _read("app/workers/review_worker.py")
    bare = re.search(r'=\s*["\']github:review_queue["\']', worker_src)
    if bare:
        record("constants:queue_key_single_source", FAIL,
               "bare 'github:review_queue' assignment still in review_worker.py")
    else:
        record("constants:queue_key_single_source", PASS,
               "no duplicate queue key string in review_worker.py")


def check_reviews_api_202() -> None:
    src = _read("app/api/reviews.py")
    has_202 = "202" in src
    has_json_resp = "JSONResponse" in src
    if has_202 and has_json_resp:
        record("reviews_api:202_for_in_progress", PASS,
               "JSONResponse(status_code=202) present")
    else:
        record("reviews_api:202_for_in_progress", FAIL,
               f"202={'yes' if has_202 else 'missing'} "
               f"JSONResponse={'yes' if has_json_resp else 'missing'}")


def check_reviews_api_worker_status() -> None:
    src = _read("app/api/reviews.py")
    has_route = "/worker/status" in src
    has_handler = "get_worker_status" in src
    if has_route and has_handler:
        record("reviews_api:worker_status_endpoint", PASS,
               "GET /worker/status route and handler present")
    else:
        record("reviews_api:worker_status_endpoint", FAIL,
               f"route={'yes' if has_route else 'missing'} "
               f"handler={'yes' if has_handler else 'missing'}")


def check_run_worker_uses_running_loop() -> None:
    src = _read("scripts/run_worker.py")
    # Strip comment lines so references like "# get_event_loop() is deprecated"
    # don't produce false positives.
    code = "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    )
    if "get_running_loop" in code and "get_event_loop" not in code:
        record("run_worker:get_running_loop", PASS,
               "asyncio.get_running_loop() used (not deprecated get_event_loop)")
    elif "get_event_loop" in code:
        record("run_worker:get_running_loop", FAIL,
               "deprecated asyncio.get_event_loop() still present in non-comment code")
    else:
        record("run_worker:get_running_loop", SKIP,
               "neither get_running_loop nor get_event_loop found")


# ── Runtime checks (require project venv with all deps) ───────────────────────

async def check_redis_reachable() -> None:
    try:
        from app.services.redis_service import ping_redis  # noqa: PLC0415
        ok = await ping_redis()
        if ok:
            record("redis:reachable", PASS)
        else:
            record("redis:reachable", FAIL, "ping returned False — is Redis running?")
    except ImportError as exc:
        record("redis:reachable", SKIP,
               f"import failed (activate project venv first): {exc}")
    except Exception as exc:
        record("redis:reachable", FAIL, str(exc))


async def check_worker_heartbeat_key(require_alive: bool = False) -> None:
    try:
        from app.services.redis_service import get_redis_client  # noqa: PLC0415
        from app.core.constants import WORKER_HEARTBEAT_KEY     # noqa: PLC0415
        client = await get_redis_client()
        raw = await client.get(WORKER_HEARTBEAT_KEY)
        if raw is None:
            status_label = FAIL if require_alive else SKIP
            detail = "key absent — worker not running?"
            if not require_alive:
                detail += " (start it to verify; skipping)"
            record("worker:heartbeat_key_exists", status_label, detail)
            return
        data = json.loads(raw)
        record("worker:heartbeat_key_exists", PASS,
               f"status={data.get('status')} updated_at={data.get('updated_at')}")
    except ImportError as exc:
        record("worker:heartbeat_key_exists", SKIP,
               f"import failed (activate project venv first): {exc}")
    except Exception as exc:
        record("worker:heartbeat_key_exists", FAIL, str(exc))


async def check_graph_state_has_metadata(delivery_id: str) -> None:
    try:
        from app.services.graph_state_store import get_graph_state  # noqa: PLC0415
        state = await get_graph_state(delivery_id)
        if state is None:
            record("graph_state:metadata_fields", FAIL,
                   f"delivery_id '{delivery_id}' not found in Redis")
            return
        required = ["installation_id", "owner", "repo", "head_sha", "base_sha",
                    "repository", "pr_number"]
        missing = [f for f in required if state.get(f) is None]
        present_vals = {f: state.get(f) for f in ["repository", "pr_number", "status"]}
        if not missing:
            record("graph_state:metadata_fields", PASS,
                   f"all {len(required)} fields present — {present_vals}")
        else:
            record("graph_state:metadata_fields", FAIL,
                   f"fields with null value: {missing} (state: {present_vals})")
    except ImportError as exc:
        record("graph_state:metadata_fields", SKIP,
               f"import failed (activate project venv first): {exc}")
    except Exception as exc:
        record("graph_state:metadata_fields", FAIL, str(exc))


async def check_result_store_roundtrip() -> None:
    _TEST_ID = "validate_phase55_roundtrip"
    try:
        from app.schemas.review_result import ReviewResult, ReviewSummary  # noqa: PLC0415
        from app.services.review_result_store import (  # noqa: PLC0415
            get_review_result, save_review_result,
        )
        from app.services.redis_service import get_redis_client  # noqa: PLC0415

        dummy = ReviewResult(
            delivery_id=_TEST_ID,
            repository="validate/test",
            pr_number=0,
            provider="test",
            model="test",
            findings=[],
            summary=ReviewSummary(
                verdict="approve",
                risk_level="low",
                severity_score=0,
                summary_text="Phase 5.5 validation roundtrip.",
            ),
            reviewed_files=[],
            skipped_files=[],
        )

        await save_review_result(_TEST_ID, dummy)
        loaded = await get_review_result(_TEST_ID)

        # Clean up test key immediately
        client = await get_redis_client()
        await client.delete(f"github:review_result:{_TEST_ID}")

        if loaded is not None and loaded.delivery_id == _TEST_ID:
            record("result_store:roundtrip", PASS, "write → read → delete OK")
        else:
            record("result_store:roundtrip", FAIL,
                   f"loaded={loaded!r}")
    except ImportError as exc:
        record("result_store:roundtrip", SKIP,
               f"import failed (activate project venv first): {exc}")
    except Exception as exc:
        record("result_store:roundtrip", FAIL, str(exc))


# ── Main ───────────────────────────────────────────────────────────────────────

async def run_checks(
    delivery_id: str | None,
    full: bool,
    require_worker: bool,
) -> None:
    print()
    print("  Phase 5.5 Hardening — Readiness Validation")
    print("  " + "=" * 50)

    print()
    print("  [Static checks — source file inspection, no imports required]")
    print()

    check_config_timeout()
    check_constants_queue_key()
    check_constants_heartbeat_key()
    check_review_status_literal()
    check_review_state_uses_status_type()
    check_graph_state_phase6_fields()
    check_mark_graph_state_failed()
    check_save_state_safe_helper()
    check_finalize_fatal_on_result_failure()
    check_worker_job_timeout()
    check_worker_backoff()
    check_worker_heartbeat_loop()
    check_worker_heartbeat_uses_constants()
    check_queue_key_not_duplicated()
    check_reviews_api_202()
    check_reviews_api_worker_status()
    check_run_worker_uses_running_loop()

    print()
    print("  [Runtime checks — require project venv + running Redis]")
    print()

    await check_redis_reachable()
    await check_worker_heartbeat_key(require_alive=require_worker)

    if delivery_id:
        print()
        print(f"  [Graph state metadata — delivery_id={delivery_id}]")
        print()
        await check_graph_state_has_metadata(delivery_id)

    if full:
        print()
        print("  [Result store roundtrip write/read test]")
        print()
        await check_result_store_roundtrip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate Phase 5.5 hardening requirements."
    )
    parser.add_argument(
        "--delivery-id", metavar="ID",
        help="Check a real delivery's graph state for Phase 6 metadata fields",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Run the result store roundtrip write/read test",
    )
    parser.add_argument(
        "--require-worker", action="store_true",
        help="Fail (not skip) if worker heartbeat key is absent",
    )
    args = parser.parse_args()

    asyncio.run(run_checks(
        delivery_id=args.delivery_id,
        full=args.full,
        require_worker=args.require_worker,
    ))

    print()
    passed  = sum(1 for _, s, _ in _results if s == PASS)
    failed  = sum(1 for _, s, _ in _results if s == FAIL)
    skipped = sum(1 for _, s, _ in _results if s == SKIP)
    total   = len(_results)

    print(f"  Results: {passed} passed, {failed} failed, {skipped} skipped / {total} total")
    print()

    if failed:
        print("  Failed checks:")
        for name, status, detail in _results:
            if status == FAIL:
                print(f"    FAIL  {name}" + (f" — {detail}" if detail else ""))
        print()
        sys.exit(1)
    else:
        print("  All checks passed.")
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()
