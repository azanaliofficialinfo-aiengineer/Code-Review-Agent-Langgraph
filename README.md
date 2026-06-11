# CodeReview Agent

> Autonomous AI-powered GitHub PR reviewer — built with FastAPI, LangGraph, and Next.js.

---

## Overview

CodeReview Agent integrates with GitHub as a GitHub App. When a pull request is opened or updated, it automatically:

1. Receives the webhook event
2. Fetches the changed files and diff via GitHub API
3. Runs an AI review pipeline (LangGraph + Groq / NVIDIA / Claude)
4. Posts structured inline review comments back to the PR
5. Stores review history in PostgreSQL, surfaced in a Next.js dashboard

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI 0.111, Python 3.12 |
| AI Orchestration | LangGraph 0.2 |
| AI Provider | Groq (primary), NVIDIA NIM / Anthropic (planned) |
| Database | PostgreSQL 16 + SQLAlchemy 2 (async) |
| Cache / Queue | Redis 7 |
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui |
| Containerisation | Docker Compose |

---

## Local Setup

### Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- Node.js 20+ (for local frontend development)
- Python 3.12+ (for local backend development)

### 1. Clone the repo

```bash
git clone https://github.com/your-org/codereview-agent.git
cd codereview-agent
```

### 2. Configure environment variables

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Edit `backend/.env` and fill in:
- `GITHUB_WEBHOOK_SECRET`, `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY`
- `GROQ_API_KEY`

### 3. Start all services with Docker Compose

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

### 4. Run services individually (development)

**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Infrastructure only (postgres + redis):**
```bash
docker compose up postgres redis
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Default |
|---|---|---|
| `APP_NAME` | Application display name | `CodeReview Agent` |
| `ENVIRONMENT` | `development` / `staging` / `production` | `development` |
| `DATABASE_URL` | PostgreSQL async connection string | — |
| `REDIS_URL` | Redis connection string | `redis://redis:6379` |
| `GITHUB_WEBHOOK_SECRET` | Secret token for verifying GitHub webhook payloads | — |
| `GITHUB_APP_ID` | GitHub App numeric ID | — |
| `GITHUB_PRIVATE_KEY` | PEM-encoded private key from GitHub App | — |
| `GROQ_API_KEY` | API key from console.groq.com | — |
| `AI_PROVIDER` | Active AI provider: `groq` / `nvidia` / `anthropic` | `groq` |
| `GITHUB_DRY_RUN` | `true` = store payload, skip GitHub API; `false` = post live review | `true` |
| `REVIEW_JOB_TIMEOUT_SECONDS` | Per-job wall-clock cap (asyncio.wait_for) | `300` |

### Frontend (`frontend/.env`)

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend base URL exposed to the browser |

---

## Phase Roadmap

| Phase | Title | Status |
|---|---|---|
| **1** | Project Setup — monorepo, Docker, health checks | ✅ **Complete** |
| **2** | GitHub App + Webhook — receive & verify PR events | ✅ **Complete** |
| **3** | PR Data Fetching — files, diffs, metadata via GitHub API | ✅ **Complete** |
| **4** | Groq AI Review — structured AI-powered code review | ✅ **Complete** |
| **5** | LangGraph Workflow — multi-step agentic review pipeline | ✅ **Complete** |
| **5.5** | Hardening — reliability, metadata, timeout, heartbeat | ✅ **Complete** |
| **6** | GitHub Comments — post inline review comments to PRs | ✅ **Complete** |
| **7** | Database + Dashboard — store reviews, surface in UI | ✅ **Complete** |
| **7.5** | Persistence + API Hardening — pagination, auth, fallback | ✅ **Complete** |
| **8A** | Dashboard + Analytics APIs — 6 pages, 5 analytics endpoints | ✅ **Complete** |
| **8A.5** | Deployment Readiness Fix Sprint — CORS, Docker, a11y, mobile | ✅ **Complete** |
| **8B** | Production Deploy — Railway / Render, CI/CD, rate limits | 🔲 Planned |

---

## Project Structure

```
codereview-agent/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app entry point
│   │   ├── api/               # Route handlers
│   │   │   └── health.py      # /health + /health/ready
│   │   ├── core/
│   │   │   └── config.py      # Pydantic settings
│   │   ├── db/
│   │   │   └── session.py     # SQLAlchemy engine + session factory
│   │   ├── models/            # ORM models (Phase 7)
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   ├── services/          # Business logic layer
│   │   └── graph/             # LangGraph nodes & edges (Phase 5)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── page.tsx           # Landing page
│   │   ├── layout.tsx         # Root layout
│   │   └── globals.css        # Tailwind base styles
│   ├── components/            # Shared UI components (shadcn/ui, Phase 7)
│   ├── lib/
│   │   └── utils.ts           # cn() helper
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── Dockerfile
│   └── .env.example
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## Phase 6 — GitHub Review Comment System

Phase 6 takes the `ReviewResult` produced by the LangGraph pipeline and converts
it into a GitHub pull-request review — a structured payload with a summary body
and zero or more inline code comments.

### Architecture

```
ReviewResult (Redis)
        +
Graph State (Redis)   ──► build_review_submission()  ──► ReviewSubmission
        |                                                        │
        │                                               ┌────────┴────────┐
        │                                          Dry-Run?          Live Mode
        │                                         (default)     GITHUB_DRY_RUN=false
        │                                               │               │
        └── dedup check ────────────────────────────────┘               │
                                                  save to Redis    POST /pulls/.../reviews
                                                  (48 h TTL)        + save to Redis
```

### Dry-Run Mode (Default)

```bash
# backend/.env
GITHUB_DRY_RUN=true   # default — build and store payload, do NOT call GitHub
```

With `GITHUB_DRY_RUN=true` the worker builds the full GitHub review payload and
stores it in Redis under `github:review_submission:{delivery_id}` (TTL: 48 h).
No GitHub API call is made.  Inspect the payload:

```bash
# Public inspection endpoint
curl http://localhost:8000/reviews/<delivery_id>/submission | python -m json.tool

# Dev/staging only (includes routing metadata)
curl http://localhost:8000/debug/review-submission/<delivery_id> | python -m json.tool
```

### Live Review Submission

```bash
# backend/.env
GITHUB_DRY_RUN=false   # build payload AND post it to GitHub
```

The worker calls `POST /repos/{owner}/{repo}/pulls/{pr_number}/reviews` using a
per-installation bearer token obtained from the GitHub App JWT exchange (Phase 3).
The token is never logged.

### Review Payload Structure

```json
{
  "repository": "owner/repo",
  "owner": "owner",
  "repo": "repo",
  "pr_number": 42,
  "commit_id": "abc123def456",
  "event": "REQUEST_CHANGES",
  "body": "## 🤖 CodeReview Agent Review\n\nVerdict: REQUEST_CHANGES\n...",
  "comments": [
    {
      "file_path": "src/auth.py",
      "line": 87,
      "body": "⚠️ High — Security\n\nPotential SQL injection...",
      "severity": "high",
      "category": "security"
    }
  ]
}
```

### Verdict Rules

| Findings present | GitHub event |
|---|---|
| One or more `critical` or `high` | `REQUEST_CHANGES` |
| Only `medium` (no critical/high) | `COMMENT` |
| No actionable findings | `APPROVE` |

### Inline Comment Format

```
⚠️ High — Security

Potential SQL injection risk detected.

Suggestion:
Use parameterized queries.

Confidence: 91%
```

A finding becomes an inline comment only when **both** conditions hold:
- `should_comment = true` (confidence ≥ threshold, severity ≥ medium, category ≠ style)
- `line` is not `null` and is a positive integer

Findings that don't meet these criteria are captured in the aggregate summary only.

### Duplicate Prevention

Before submitting a review, the worker checks `github:review_lock:{delivery_id}`
(TTL: 24 h).  If the key exists the submission is skipped — this prevents
double-posting when GitHub redelivers a webhook.

The lock is set **after** a successful submission so that a failed attempt is
always retryable.

### New Endpoints

| Endpoint | Description |
|---|---|
| `GET /reviews/{id}/submission` | Stored `ReviewSubmission` payload (public) |
| `GET /debug/review-submission/{id}` | Same, dev/staging only, returns 404 in prod |

### Validation

```bash
cd backend
python scripts/test_review_builder.py
```

Tests:
- Verdict mapping (critical/high → REQUEST\_CHANGES, medium → COMMENT, none → APPROVE)
- Summary body sections present
- Inline comment generation (eligible vs. skipped)
- Comment body format (icon, severity, category, confidence)
- Error on missing graph-state fields
- Dedup lock (requires Redis)
- Dry-run storage round-trip (requires Redis)

---

## Phase 5.5 — Hardening

Phase 5.5 resolves all reliability and data-availability issues identified in
the Phase 5 engineering audit before GitHub comment posting (Phase 6) begins.

### What Changed

#### 1. GitHub Metadata Persistence

Phase 6 comment posting requires `installation_id` and `head_sha` to authenticate
with GitHub and identify the commit to review.  These are now written to the
`github:graph_state:{delivery_id}` Redis record every time a graph state is saved:

| Field stored | Source | Used in Phase 6 |
|---|---|---|
| `installation_id` | `PRContext.metadata` | Exchange GitHub App JWT for bearer token |
| `owner` | `PRContext.metadata` | REST API path parameter |
| `repo` | `PRContext.metadata` | REST API path parameter |
| `head_sha` | `PRContext.metadata` | Identifies the commit for a PR review |
| `base_sha` | `PRContext.metadata` | Diff reference |

All five fields survive worker restarts — they are persisted to Redis with a
48-hour TTL as soon as `fetch_context_node` completes.

#### 2. Reliable State Persistence

Every `save_graph_state` call in all four graph nodes is now wrapped in
`_save_state_safe()`, which catches and logs Redis errors without letting them
propagate into the node's error-handling path.  A Redis outage during graph
execution can no longer cause a job to silently disappear.

#### 3. Result Persistence Consistency

`finalize_node` previously reported `status=completed` even if
`save_review_result` failed — leaving the `/result` endpoint permanently
returning 404 for a "completed" job.

Now: `save_review_result` failure is treated as fatal.  The node transitions
to `status=failed` with a clear error message.  `completed` only appears when
the full `ReviewResult` is confirmed stored.

#### 4. Centralized Redis Keys

All Redis key strings live in `app/core/constants.py` — the single source of
truth.  `REVIEW_QUEUE_KEY` is no longer duplicated between `redis_service.py`
and `review_worker.py`.

#### 5. Job Timeout

Each review job is wrapped in `asyncio.wait_for()`:

```bash
# backend/.env
REVIEW_JOB_TIMEOUT_SECONDS=300   # default: 5 minutes
```

On timeout:
- Worker logs the event and calls `mark_graph_state_failed()` to update the
  Redis record to `status=failed` (preserving any already-saved metadata).
- Worker continues to the next job.

#### 6. Redis Failure Backoff

Redis errors in the worker main loop back off exponentially instead of
retrying every second:

```
1s → 2s → 4s → 8s → 16s → 30s (max)
```

The counter resets on the first successful loop iteration.  A 10-minute Redis
outage generates ~12 error log lines (not ~600).

#### 7. Worker Heartbeat

The worker writes to `github:worker:heartbeat` (TTL 30 s) every 10 seconds.
A missing key means the worker is dead or has never started.

```bash
# Poll worker liveness
curl http://localhost:8000/reviews/worker/status
# {"status":"alive","updated_at":"2024-01-15T10:00:00Z","last_heartbeat_ago_seconds":3.1}
```

#### 8. Improved API Semantics

`GET /reviews/{delivery_id}/result` previously returned **404** for in-progress
reviews — indistinguishable from "does not exist".  Now:

| Status | HTTP | Meaning |
|---|---|---|
| Not found / expired | **404** | Truly does not exist |
| `queued` / `fetching_context` / `reviewing` | **202** | In progress — retry later |
| `failed` | **422** | Pipeline failed — see `error` field |
| `completed` | **200** | Full `ReviewResult` body |

#### 9. Stronger Type Safety

`status: str` in `ReviewState` is replaced by:

```python
ReviewStatus = Literal["queued", "fetching_context", "reviewing", "completed", "failed"]
```

A typo in a status assignment is now a static type error, not a silent
routing failure in the LangGraph conditional edges.

### Validate Phase 5.5

```bash
cd backend

# Core static + Redis checks (no running worker required)
python scripts/validate_phase55.py

# Also check a specific delivery's stored metadata
python scripts/validate_phase55.py --delivery-id <delivery_id>

# Full: include result store write/read roundtrip
python scripts/validate_phase55.py --full

# Fail (not skip) if worker heartbeat is absent
python scripts/validate_phase55.py --require-worker
```

---

## Phase 5 — LangGraph Workflow + Review Worker

### Architecture

When a `pull_request` webhook is accepted, the delivery ID is pushed onto
`github:review_queue`.  The worker pops it and runs the review graph:

```
webhook → Redis queue → ReviewWorker (BLPOP)
                              ↓
                    run_review_graph(delivery_id)
                              ↓
              START → fetch_context → review_pr → finalize → END
                           ↓                 ↓
                        failure           failure
                           ↓                 ↓
                           └────── END ───────┘
```

Each node saves a lightweight state snapshot to Redis (`github:graph_state:{delivery_id}`)
so the status can be polled at any time.  The full `ReviewResult` is stored separately
under `github:review_result:{delivery_id}` (TTL: 48 h for both keys).

### Start the Worker

```bash
cd backend
python scripts/run_worker.py
```

The worker blocks on `BLPOP github:review_queue` and processes each job through the
full LangGraph pipeline.  Individual job failures are logged and swallowed — the
worker never crashes on per-review errors.  Ctrl+C / SIGTERM triggers graceful shutdown
(the worker finishes the current job, then exits).

### Poll Review Status

```bash
# Check current pipeline status (queued / fetching_context / reviewing / completed / failed)
curl http://localhost:8000/reviews/<delivery_id>/status | python -m json.tool

# Retrieve full ReviewResult once status == "completed"
curl http://localhost:8000/reviews/<delivery_id>/result | python -m json.tool
```

| Status value | Meaning |
|---|---|
| `queued` | Job is in the Redis queue, worker hasn't picked it up yet |
| `fetching_context` | Worker is fetching PR data from GitHub |
| `reviewing` | AI provider is running the review |
| `completed` | Review finished — result available at `/result` |
| `failed` | Pipeline error — see `error` field in `/status` |

### Debug Endpoint (dev/staging only)

```bash
# Inspect the full graph execution state snapshot
curl http://localhost:8000/debug/graph-state/<delivery_id> | python -m json.tool
```

### End-to-End Test Flow

```bash
# 1. Start all services
docker compose up postgres redis backend

# 2. In a separate terminal, start the worker
cd backend && python scripts/run_worker.py

# 3. Send a test webhook (Phase 2 script) — note the delivery_id
GITHUB_WEBHOOK_SECRET=<your-secret> python scripts/test_webhook_signature.py

# 4. Poll status until completed
curl http://localhost:8000/reviews/<delivery_id>/status

# 5. Retrieve the full result
curl http://localhost:8000/reviews/<delivery_id>/result | python -m json.tool
```

---

## Phase 4 — Groq AI Review

### Set GROQ_API_KEY

```bash
# backend/.env
GROQ_API_KEY=gsk_...your_key_here...
```

> **Never commit your API key.** `.env` is in `.gitignore`.

### Choose a Model

The model is controlled entirely by `GROQ_MODEL` in `backend/.env`:

```bash
# Default (set per project requirement)
GROQ_MODEL=openai/gpt-oss-120b

# Alternatives — all configurable without code changes:
GROQ_MODEL=llama-3.3-70b-versatile   # reliable, widely available
GROQ_MODEL=qwen/qwen3-32b            # strong code reasoning
```

> If `openai/gpt-oss-120b` is unavailable on your Groq tier, switch to
> `llama-3.3-70b-versatile` — it fully supports JSON mode and performs well on code review tasks.

### Run the Debug Review Endpoint

After receiving a webhook (or using the Phase 2 test script):

```bash
curl http://localhost:8000/debug/review-result/<delivery_id> | python -m json.tool
```

Response includes:
- `findings[]` — per-file findings with severity, category, confidence
- `summary` — verdict, risk level, severity score
- `reviewed_files` / `skipped_files`
- `_debug.elapsed_seconds` — total wall time for the review

### Run the CLI Review Helper

```bash
cd backend

# Summary view
python scripts/review_pr.py <delivery_id>

# Full descriptions + suggestions
python scripts/review_pr.py <delivery_id> --verbose
```

### Run the Parsing Tests

```bash
cd backend
python scripts/test_review_parsing.py
# → 44/44 tests pass, no external services needed
```

Tests cover: JSON extraction fallback, line-number parsing, confidence filtering,
`should_comment` enforcement, summary scoring, risk-level boundaries.

### AI Behaviour Notes

| Setting | Default | Effect |
|---|---|---|
| `AI_MAX_FILES` | `20` | Files above this limit are skipped (noted in `skipped_files`) |
| `AI_MAX_PATCH_CHARS_PER_FILE` | `12000` | Large diffs are truncated with a marker before being sent |
| `AI_MIN_CONFIDENCE` | `0.65` | Findings below this threshold are removed from the result |

**Comments are not posted until Phase 6.** This phase only produces a `ReviewResult`.

### Open Models vs Claude

| Capability | Groq (llama/qwen) | Claude |
|---|---|---|
| JSON mode | Yes | Yes |
| Line precision | Moderate | High |
| Security depth | Good | Excellent |
| False positive rate | Higher | Lower |
| Cost | Free tier available | Token-based |

For production accuracy, swap `AI_PROVIDER=anthropic` in Phase 8 (no code changes needed after the Anthropic provider class is implemented).

---

## Phase 3 — PR Data Fetching

### GitHub App Private Key Setup

1. Go to **GitHub → Settings → Developer Settings → GitHub Apps → Your App → Private keys**
2. Generate and download the `.pem` file
3. In `backend/.env`, set the key as a single escaped string:

```bash
GITHUB_APP_ID=123456
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nMIIEo...\n-----END RSA PRIVATE KEY-----"
```

> The backend normalises `\n` escape sequences automatically — no need to convert to a real multi-line value.

### `installation_id` Requirement

Every actionable webhook payload sent by a GitHub App includes an `installation` object:

```json
{ "installation": { "id": 987654 } }
```

This ID is required to exchange the App JWT for a per-repository access token.
Webhooks sent from raw repository settings (not a GitHub App) will not include it and will be rejected at the fetching stage with a `MissingInstallationError`.

### Redis Queue

After a valid `pull_request` webhook is accepted, the delivery ID is pushed onto a Redis list:

```
Key  : github:review_queue
Type : Redis list (FIFO — rpush / lpop)
```

```bash
# Inspect queue depth
docker compose exec redis redis-cli LLEN github:review_queue

# Peek at next item without consuming it
docker compose exec redis redis-cli LINDEX github:review_queue 0
```

The LangGraph worker (Phase 5) will consume jobs from this queue using `blpop`.

### Debug Endpoint

Available in `development` and `staging` only (returns 404 in production).

```bash
# After receiving a real or test webhook, use the delivery_id to inspect the full context:
curl http://localhost:8000/debug/pr-context/<delivery_id> | python -m json.tool
```

The response is a full `PRContext` JSON including PR metadata, all changed files, and totals.

### CLI Fetch Helper

```bash
cd backend

# Summary view
python scripts/fetch_pr_context.py <delivery_id>

# With file patches
python scripts/fetch_pr_context.py <delivery_id> --verbose
```

Exit codes: `0` success · `1` not found / bad payload · `2` GitHub API error · `3` unexpected

### End-to-End Test Flow

```bash
# 1. Start infrastructure + backend
docker compose up postgres redis backend

# 2. Send a test webhook (from Phase 2 script)
cd backend
GITHUB_WEBHOOK_SECRET=<your-secret> python scripts/test_webhook_signature.py
# Paste the printed curl command — note the returned delivery_id

# 3. Inspect stored payload
docker compose exec redis redis-cli GET github:webhook:<delivery_id>

# 4. Fetch full PR context (requires real GITHUB_APP_ID + GITHUB_PRIVATE_KEY)
curl http://localhost:8000/debug/pr-context/<delivery_id>
# or
python scripts/fetch_pr_context.py <delivery_id>
```

> **Note:** Steps 4+ require a real GitHub App installation. The test webhook script generates a synthetic payload without a real `installation.id` — to test PR fetching end-to-end, configure your GitHub App to send webhooks to an `ngrok` tunnel pointing at `localhost:8000/webhooks/github`.

### AI Review starts in Phase 4

The `PRContext` object built in this phase is the direct input to the Groq AI reviewer (Phase 4) and the LangGraph orchestration pipeline (Phase 5).

---

## Phase 2 — GitHub Webhook Testing

### 1. Set your webhook secret

In `backend/.env`, set a strong random value:

```bash
GITHUB_WEBHOOK_SECRET=replace-with-a-random-32-char-string
```

> For local testing only, `test-secret` is fine as long as the script uses the same value.

### 2. Start the backend

```bash
# Docker (postgres + redis + backend together):
docker compose up postgres redis backend

# Or locally:
cd backend
uvicorn app.main:app --reload --port 8000
```

### 3. Verify readiness

```bash
curl http://localhost:8000/health/ready
# {"status":"ready","checks":{"redis":"ok","database":"not_configured"}}
```

### 4. Generate a test signature and curl command

```bash
cd backend
GITHUB_WEBHOOK_SECRET=test-secret python scripts/test_webhook_signature.py
```

The script prints a ready-to-paste `curl` command with a valid `X-Hub-Signature-256` header.

To test a different PR action:

```bash
GITHUB_WEBHOOK_SECRET=test-secret WEBHOOK_ACTION=synchronize \
  python scripts/test_webhook_signature.py
```

### 5. Accepted PR actions

| Action | Result |
|---|---|
| `opened` | `{"status":"accepted", ...}` |
| `synchronize` | `{"status":"accepted", ...}` |
| `reopened` | `{"status":"accepted", ...}` |
| `closed` / any other | `{"status":"ignored","reason":"unsupported_pull_request_action"}` |

### 6. Error responses

| Condition | HTTP status | Detail |
|---|---|---|
| Wrong / missing signature | `401` | `"Invalid or missing webhook signature"` |
| Missing `X-GitHub-Event` | `400` | `"Missing X-GitHub-Event header"` |
| Event is not `pull_request` | `422` | `"Unsupported event: '...' "` |
| Non-JSON body | `400` | `"Request body is not valid JSON"` |

### 7. Inspect stored payload in Redis

```bash
# Connect to the Redis container:
docker compose exec redis redis-cli

# List stored webhook keys:
KEYS github:webhook:*

# Inspect a specific delivery:
GET github:webhook:<delivery-id>
```

---

## Phase 7.5 — Persistence + API Hardening

Phase 7.5 hardened the PostgreSQL persistence layer and REST API before adding new features. None of the changes alter the Redis-based webhook/review flow visible to GitHub.

### Why it was needed

The Phase 7 audit identified 9 production blockers:

| # | Issue | Risk |
|---|-------|------|
| 1 | `dry_run=True` hardcoded in `persistence_service.py` | Wrong values written to DB |
| 2 | `installation_id` silently defaulted to 0 | Invalid foreign key relationships |
| 3 | Duplicate BTree indexes (UNIQUE + explicit `Index()`) | Wasted write overhead |
| 4 | No pagination totals on list endpoints | Clients can't paginate |
| 5 | 6-query N+1 in `get_review_detail` | Slow under load |
| 6 | No findings pagination | Unbounded response sizes |
| 7 | No API authentication | Open to anyone with the URL |
| 8 | No status filter validation | Silent wrong results |
| 9 | Redis-only `/status` and `/result` | Breaks after 48h TTL |

### API authentication

Auth is **disabled by default** (development mode). To enable:

```env
API_AUTH_ENABLED=true
API_AUTH_TOKEN=your-secret-token-here
```

Auth is automatically enforced when `ENVIRONMENT=production` regardless of `API_AUTH_ENABLED`.

Protected endpoints require `Authorization: Bearer <token>`. The webhook endpoint (`/webhooks/github`) is **never** protected — GitHub must be able to reach it without credentials.

### Pagination format

All list endpoints now return a consistent wrapper:

```json
{
  "items": [...],
  "total": 142,
  "limit": 20,
  "offset": 0
}
```

Endpoints affected: `GET /reviews`, `GET /repositories`, `GET /repositories/{owner}/{repo}/reviews`.

The `GET /reviews/{delivery_id}` detail endpoint paginates findings separately:

```
GET /reviews/{delivery_id}?findings_limit=50&findings_offset=0
```

`findings` in the response body is:

```json
{
  "items": [...],
  "total": 87,
  "limit": 50,
  "offset": 0
}
```

### Redis → Postgres fallback

`GET /reviews/{delivery_id}/status` and `GET /reviews/{delivery_id}/result` now fall back to PostgreSQL when the 48-hour Redis TTL has expired. Fallback responses include `"source": "database"` to indicate which backend answered.

### Index cleanup

Migration `0002_fix_indexes` removes duplicate BTree indexes (a `UNIQUE` constraint already creates one; an explicit `Index(...)` on the same column creates a second):

- Removed: `ix_repositories_full_name`, `ix_review_jobs_delivery_id`, `ix_review_findings_review_job_id`, `ix_pull_requests_pr_number`
- Added: `ix_review_jobs_repo_created (repository_id, created_at)`, `ix_review_jobs_status_created (status, created_at)`, `ix_review_findings_job_severity (review_job_id, severity)`

Apply with:

```bash
cd backend
alembic upgrade head
```

### Validate Phase 7.5

```bash
cd backend
python scripts/validate_phase75.py

# With a live database:
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname python scripts/validate_phase75.py
```

Expected: **56 PASS, 0 FAIL**.

---

## Phase 8A — Dashboard + Analytics APIs

Phase 8A adds a full-stack analytics dashboard on top of the Phase 7.5 persistence layer. No billing, no multi-tenant auth, no deployment changes.

### What was built

**Backend analytics APIs** (`GET /analytics/*`) — 5 new endpoints backed exclusively by PostgreSQL aggregate queries:

| Endpoint | Description |
|----------|-------------|
| `GET /analytics/overview` | Metric card data: totals, success rate, avg score, avg duration |
| `GET /analytics/reviews-per-day?days=14` | Daily review counts with date-gap filling |
| `GET /analytics/severity-distribution` | Finding counts by severity level |
| `GET /analytics/verdict-distribution` | Review verdicts breakdown |
| `GET /analytics/risk-trend?days=14` | Daily average severity score trend |

All analytics endpoints use the same bearer-token auth as `/reviews/*` and `/repositories/*`.

**Frontend dashboard** — 6 pages built with Next.js App Router, Tailwind CSS, and Recharts:

| Route | Description |
|-------|-------------|
| `/` | Upgraded landing page with pipeline visual and feature cards |
| `/dashboard` | Overview: 6 metric cards + 4 charts + recent reviews table |
| `/reviews` | Paginated review list with status/repository filters |
| `/reviews/[deliveryId]` | Full review detail: PR info, findings (paginated), submission |
| `/repositories` | Repository cards with review counts and last activity |
| `/repositories/[owner]/[repo]` | Per-repo review history table |

### Environment variables

```env
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000        # backend base URL
NEXT_PUBLIC_API_AUTH_TOKEN=                     # optional bearer token (leave empty in dev)
```

### Running the frontend

```bash
cd frontend
npm install
npm run dev       # → http://localhost:3000
npm run build     # production build
npm run type-check  # TypeScript validation
```

### Running the backend analytics API

```bash
cd backend
uvicorn app.main:app --reload   # analytics endpoints register automatically
```

### Screens to manually test

1. `http://localhost:3000` — landing page
2. `http://localhost:3000/dashboard` — metric cards + 4 charts (empty-state safe)
3. `http://localhost:3000/reviews` — list with status filter
4. `http://localhost:3000/reviews/<delivery_id>` — detail with findings accordion
5. `http://localhost:3000/repositories` — repository cards
6. `http://localhost:3000/repositories/<owner>/<repo>` — per-repo reviews
7. `http://localhost:8000/docs` → `GET /analytics/overview` — JSON response

### Empty-state behavior

All pages render correctly with zero data:
- Dashboard shows `0` in metric cards with animated counters
- Charts render empty donut outlines with "No data yet" text
- Tables show illustrated empty states with descriptive copy
- Reviews-per-day chart fills the full date range with zeros

### Design system

- Dark glassmorphism cards: `bg-white/[0.025] border border-white/6`
- Severity colors: critical=red, high=orange, medium=yellow, low=teal
- Recharts with custom dark tooltips and gradient fills
- Skeleton shimmer loading states on all data surfaces
- Animated metric counter (ease-out cubic, 900ms)
- Sticky sidebar with active-route indicator
- Route group `(dashboard)` isolates the AppShell from the landing page

### Validate Phase 8A

```bash
# Backend (19 checks)
cd backend && python scripts/validate_phase8a.py

# Frontend (54 checks)
cd frontend && node scripts/validate_phase8a.mjs
```

Expected: **19 PASS backend · 54 PASS frontend · 0 FAIL**.

---

## Phase 8A.5 — Deployment Readiness Fix Sprint

Phase 8A.5 addresses every deployment blocker identified in the Phase 8A audit before Phase 8B production work begins. No new features, no UI redesign — targeted fixes only.

### What was fixed

#### 1. CORS misconfiguration (critical)

`allow_origins=["*"]` combined with `allow_credentials=True` is invalid per the CORS spec and rejected by browsers (Starlette 0.27+ raises at startup).

- Added `BACKEND_CORS_ORIGINS` and `ALLOW_CREDENTIALS` to `config.py` with a `field_validator` that parses a comma-separated env string into `list[str]`.
- Introduced `_build_cors_origins()` in `main.py`: always includes `localhost:3000` in dev/staging, raises `RuntimeError` at startup if production has no origins configured, and never allows wildcard.

```env
# backend/.env
BACKEND_CORS_ORIGINS=http://localhost:3000,https://your-frontend.railway.app
ALLOW_CREDENTIALS=true
```

#### 2. Backend Dockerfile — `--reload` in production (critical)

Removed `--reload` (file-watcher, dev only), added `--workers 2`, and added a non-root `appuser` so the container doesn't run as root.

#### 3. Frontend Docker build-time env vars (critical)

`NEXT_PUBLIC_*` variables are baked into the Next.js bundle at `npm run build`, not injected at container startup. Moving them to `docker-compose environment:` had no effect.

- Frontend `Dockerfile` now accepts `ARG NEXT_PUBLIC_API_URL` before the `RUN npm run build` step.
- `docker-compose.yml` passes the value under `build.args`, not `environment:`.

```yaml
# docker-compose.yml
frontend:
  build:
    args:
      NEXT_PUBLIC_API_URL: http://localhost:8000
      # Production: NEXT_PUBLIC_API_URL=https://your-backend.railway.app
```

#### 4. WorkerStatus widget — fake hardcoded "Live" (medium)

Replaced the hardcoded status badge with a real polling component in `Sidebar.tsx`:

- Calls `GET /reviews/worker/status` on mount and every 30 seconds.
- Shows **Live** (green), **Offline** (red), **Unknown** (red), or **Checking…** (gray) based on the API response.

#### 5. Mobile sidebar — no hamburger / drawer (medium)

- `AppShell` is now a Client Component that owns `sidebarOpen` state.
- `Topbar` renders a hamburger button (`lg:hidden`) that toggles the sidebar.
- `Sidebar` uses CSS translate (`-translate-x-full lg:translate-x-0`) and slides in when `isOpen=true`.
- A semi-transparent backdrop overlay closes the sidebar on tap.
- Main content uses `lg:pl-56` so it isn't pushed on mobile.

#### 6. Analytics timezone — `date.today()` (medium)

Replaced `date.today()` with `datetime.now(timezone.utc).date()` in `analytics.py`. `date.today()` returns the server's local date, which can be off by up to ±1 day depending on the server timezone.

#### 7. `framer-motion` dead dependency (medium)

Removed `framer-motion` from `package.json` — it was imported in `package.json` but never used in the component tree. All animations (`animate-ping`, `animate-shimmer`, `animate-fade-up`) are Tailwind CSS utilities and are unaffected.

#### 8. Accessibility fixes (WCAG)

| Location | Fix |
|---|---|
| Dashboard, Reviews, Repo detail — table rows | Added `role="button"`, `tabIndex={0}`, `aria-label`, and `onKeyDown` (Enter/Space) |
| Reviews page — search input | Added `<label htmlFor="repo-filter" className="sr-only">` |
| Reviews page — status `<select>` | Added `aria-label="Filter by status"` |
| Reviews page — pagination | `aria-label="Previous page"` / `"Next page"` on chevron buttons |
| FindingCard accordion | Added `role="button"`, `tabIndex={0}`, `aria-expanded`, `onKeyDown` |

#### 9. Shared UI utilities extracted

| File | Extracted from |
|---|---|
| `frontend/lib/format.ts` — `formatDuration()` | Duplicated inline in 4 pages |
| `frontend/components/ui/Pagination.tsx` | Duplicated inline in 3 pages |
| `frontend/components/ui/ChartCard.tsx` | Inline definition in dashboard page |

All pages now import from these shared modules.

#### 10. Navigation — `window.location.href` → `router.push()`

`window.location.href` assignments trigger a full page reload and bypass the Next.js router. Replaced with `useRouter` + `router.push()` in the dashboard, reviews list, and repository detail pages.

---

### Files changed in Phase 8A.5

| File | Change |
|---|---|
| `backend/app/core/config.py` | Added `BACKEND_CORS_ORIGINS`, `ALLOW_CREDENTIALS`, `parse_cors_origins` |
| `backend/app/main.py` | Added `_build_cors_origins()`, updated `CORSMiddleware` call |
| `backend/app/api/analytics.py` | `date.today()` → `datetime.now(timezone.utc).date()` |
| `backend/Dockerfile` | Removed `--reload`, added `--workers 2`, non-root user |
| `backend/.env.example` | Documented new CORS + auth vars |
| `frontend/lib/format.ts` | Created — `formatDuration()` |
| `frontend/components/ui/Pagination.tsx` | Created — shared paginator with aria-labels |
| `frontend/components/ui/ChartCard.tsx` | Created — extracted from dashboard |
| `frontend/components/layout/AppShell.tsx` | Client component, `sidebarOpen` state, mobile overlay |
| `frontend/components/layout/Sidebar.tsx` | Mobile drawer, real WorkerStatus polling |
| `frontend/components/layout/Topbar.tsx` | Hamburger button |
| `frontend/app/(dashboard)/dashboard/page.tsx` | ChartCard, formatDuration, router.push, a11y rows |
| `frontend/app/(dashboard)/reviews/page.tsx` | Pagination, formatDuration, search label, a11y rows |
| `frontend/app/(dashboard)/reviews/[deliveryId]/page.tsx` | FindingCard keyboard accessibility |
| `frontend/app/(dashboard)/repositories/page.tsx` | Pagination component |
| `frontend/app/(dashboard)/repositories/[owner]/[repo]/page.tsx` | Pagination, formatDuration, a11y rows |
| `frontend/Dockerfile` | `ARG NEXT_PUBLIC_API_URL` before build stage |
| `frontend/.env.example` | Documents build-time requirement |
| `frontend/package.json` | Removed `framer-motion` |
| `docker-compose.yml` | `NEXT_PUBLIC_API_URL` moved to `build.args` |

### Validate Phase 8A.5

```bash
# Backend — 27 checks
cd backend && python scripts/validate_phase8a5.py

# Frontend — 60 checks
cd frontend && node scripts/validate_phase8a5.mjs
```

Expected: **27 PASS backend · 60 PASS frontend · 0 FAIL**.

---

## Contributing

1. Create a feature branch: `git checkout -b feat/your-feature`
2. Make changes and run `npm run type-check` (frontend) or `pytest` (backend)
3. Open a PR — the CodeReview Agent will review it automatically (once Phase 6 is complete)
