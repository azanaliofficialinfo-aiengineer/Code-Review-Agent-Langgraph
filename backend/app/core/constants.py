"""
Centralized Redis key constants.

Single source of truth for every Redis key string used across the codebase.
Changing a key here propagates everywhere automatically; no grep required.
"""

# ── Queue keys ────────────────────────────────────────────────────────────────

# FIFO list — delivery IDs are RPUSH'd by the webhook handler and BLPOP'd by the worker.
REVIEW_QUEUE_KEY = "github:review_queue"

# ── Worker keys ───────────────────────────────────────────────────────────────

# String (JSON) — updated every 10 s by the worker, TTL 30 s.
# Absence of this key means the worker is dead or has never started.
WORKER_HEARTBEAT_KEY = "github:worker:heartbeat"

# ── Review submission keys ────────────────────────────────────────────────────

# String ("1") — set when a review is submitted for a delivery.  TTL 24 h.
# Used by comment_dedup to detect duplicate webhook redeliveries.
REVIEW_LOCK_KEY_PREFIX = "github:review_lock:"

# String (JSON ReviewSubmission) — the generated GitHub review payload.  TTL 48 h.
# Written on every submission (both dry-run and live), used for inspection.
REVIEW_SUBMISSION_KEY_PREFIX = "github:review_submission:"
