"""
LangGraph review pipeline.

Graph flow
----------
  START
    → fetch_context   (fetches PRContext from Redis + GitHub)
      → [failed?] → failure → END
    → review_pr       (runs AI review via configured provider)
      → [failed?] → failure → END
    → finalize        (saves ReviewResult, marks completed)
      → END

Reliability contract
--------------------
  - Every node catches its own exceptions and converts them to status=failed.
  - All save_graph_state calls are wrapped in _save_state_safe() so a Redis
    outage never bypasses normal error handling or leaves a job in limbo.
  - finalize_node treats save_review_result failure as fatal — it transitions
    to status=failed rather than allowing status=completed with no result.
  - The graph always ends in either "completed" or "failed".  It never
    silently disappears.

No API keys, tokens, or full patches are ever logged.
"""
import logging
from datetime import UTC, datetime
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.graph.state import ReviewState
from app.schemas.pr_context import PRContext
from app.schemas.review_result import ReviewResult
from app.services.ai_provider import get_ai_provider
from app.services.graph_state_store import save_graph_state
from app.services.pr_fetcher import build_pr_context_from_delivery
from app.services.review_result_store import save_review_result

logger = logging.getLogger(__name__)


# ── Internal helpers ───────────────────────────────────────────────────────────

async def _save_state_safe(delivery_id: str, state: dict, ctx: str = "") -> None:
    """
    Attempt to persist graph state to Redis; log a warning on failure.

    Never raises — a Redis outage must not interrupt the graph's error-handling
    path or leave a job without a terminal status.
    """
    try:
        await save_graph_state(delivery_id, state)
    except Exception as exc:  # noqa: BLE001
        tag = f" [{ctx}]" if ctx else ""
        logger.warning(
            "[Graph] State save failed%s: delivery_id=%s error=%s",
            tag, delivery_id, exc,
        )


# ── Nodes ──────────────────────────────────────────────────────────────────────

async def fetch_context_node(state: ReviewState) -> dict:
    """Fetch PR context from the stored webhook payload + GitHub API."""
    delivery_id = state["delivery_id"]
    logger.info("[Graph] fetch_context started: delivery_id=%s", delivery_id)

    await _save_state_safe(
        delivery_id, {**state, "status": "fetching_context"}, "fetch:start"
    )

    try:
        ctx: PRContext = await build_pr_context_from_delivery(delivery_id)
        update: dict[str, Any] = {
            "status": "fetching_context",
            "pr_context": ctx.model_dump(),
        }
        logger.info(
            "[Graph] fetch_context done: delivery_id=%s repo=%s pr=%d files=%d",
            delivery_id,
            ctx.metadata.repository_full_name,
            ctx.metadata.pr_number,
            ctx.total_files,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "[Graph] fetch_context failed: delivery_id=%s error=%s",
            delivery_id, exc,
        )
        update = {
            "status": "failed",
            "error": f"Failed to fetch PR context: {type(exc).__name__}: {exc}",
        }

    await _save_state_safe(delivery_id, {**state, **update}, "fetch:done")
    return update


async def review_pr_node(state: ReviewState) -> dict:
    """Run AI review on the fetched PRContext."""
    delivery_id = state["delivery_id"]
    logger.info("[Graph] review_pr started: delivery_id=%s", delivery_id)

    await _save_state_safe(
        delivery_id, {**state, "status": "reviewing"}, "review:start"
    )

    try:
        pr_context = PRContext.model_validate(state["pr_context"])
        provider = get_ai_provider()
        result: ReviewResult = await provider.review_pr(pr_context)
        update: dict[str, Any] = {
            "status": "reviewing",
            "review_result": result.model_dump(),
        }
        logger.info(
            "[Graph] review_pr done: delivery_id=%s findings=%d verdict=%s",
            delivery_id,
            len(result.findings),
            result.summary.verdict,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "[Graph] review_pr failed: delivery_id=%s error=%s",
            delivery_id, exc,
        )
        update = {
            "status": "failed",
            "error": f"AI review failed: {type(exc).__name__}: {exc}",
        }

    await _save_state_safe(delivery_id, {**state, **update}, "review:done")
    return update


async def finalize_node(state: ReviewState) -> dict:
    """
    Persist the ReviewResult and mark the run as completed.

    Failure contract: if save_review_result raises, the node transitions to
    status=failed rather than status=completed.  This prevents the inconsistent
    state of a 'completed' job with no accessible result.
    """
    delivery_id = state["delivery_id"]
    logger.info("[Graph] finalize started: delivery_id=%s", delivery_id)

    now = datetime.now(UTC).isoformat()

    if state.get("review_result"):
        try:
            result = ReviewResult.model_validate(state["review_result"])
            await save_review_result(delivery_id, result)
        except Exception as exc:  # noqa: BLE001
            # Treat result persistence failure as fatal — "completed" without a
            # result would leave the /result endpoint permanently returning 404.
            logger.error(
                "[Graph] Failed to persist ReviewResult: delivery_id=%s error=%s",
                delivery_id, exc,
            )
            update: dict[str, Any] = {
                "status": "failed",
                "completed_at": now,
                "error": (
                    f"Failed to persist review result: {type(exc).__name__}: {exc}"
                ),
            }
            await _save_state_safe(
                delivery_id, {**state, **update}, "finalize:result_persist_failed"
            )
            return update
    else:
        logger.warning(
            "[Graph] finalize_node: review_result is absent — delivery_id=%s",
            delivery_id,
        )

    update = {"status": "completed", "completed_at": now}
    await _save_state_safe(delivery_id, {**state, **update}, "finalize:completed")
    logger.info("[Graph] finalize done: delivery_id=%s", delivery_id)
    return update


async def failure_node(state: ReviewState) -> dict:
    """Terminal failure node — records completion timestamp and logs the error."""
    delivery_id = state["delivery_id"]
    error = state.get("error") or "Unknown error"
    logger.error(
        "[Graph] Review failed: delivery_id=%s error=%s", delivery_id, error
    )

    now = datetime.now(UTC).isoformat()
    update: dict[str, Any] = {"status": "failed", "completed_at": now}
    await _save_state_safe(delivery_id, {**state, **update}, "failure:terminal")
    return update


# ── Routing ────────────────────────────────────────────────────────────────────

def _route_after_fetch(state: ReviewState) -> str:
    return "failure" if state.get("status") == "failed" else "review_pr"


def _route_after_review(state: ReviewState) -> str:
    return "failure" if state.get("status") == "failed" else "finalize"


# ── Graph compilation (module-level singleton) ─────────────────────────────────

_workflow = StateGraph(ReviewState)

_workflow.add_node("fetch_context", fetch_context_node)
_workflow.add_node("review_pr", review_pr_node)
_workflow.add_node("finalize", finalize_node)
_workflow.add_node("failure", failure_node)

_workflow.add_edge(START, "fetch_context")
_workflow.add_conditional_edges(
    "fetch_context",
    _route_after_fetch,
    {"review_pr": "review_pr", "failure": "failure"},
)
_workflow.add_conditional_edges(
    "review_pr",
    _route_after_review,
    {"finalize": "finalize", "failure": "failure"},
)
_workflow.add_edge("finalize", END)
_workflow.add_edge("failure", END)

_compiled_graph = _workflow.compile()


# ── Public helper ──────────────────────────────────────────────────────────────

async def run_review_graph(delivery_id: str) -> ReviewState:
    """
    Execute the full review pipeline for the given delivery ID.

    Returns the final accumulated state after all nodes have run.
    The returned state always has status == "completed" or "failed".

    Raises only for unexpected LangGraph-level errors; all node failures are
    captured internally and reflected in state["status"] == "failed".
    """
    initial_state: ReviewState = {
        "delivery_id": delivery_id,
        "status": "queued",
        "pr_context": None,
        "review_result": None,
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": None,
        "error": None,
    }

    # Persist the initial queued state so the /status endpoint returns
    # something meaningful before the first node has run.
    await _save_state_safe(delivery_id, initial_state, "init:queued")

    final_state: ReviewState = await _compiled_graph.ainvoke(initial_state)
    return final_state
