"""
Groq AI code reviewer.

Architecture
------------
  GroqReviewProvider.review_pr(ctx)
    → _partition_files(ctx)            partition into reviewable / skipped
    → _review_file(ctx, file)          per-file: prompt → Groq → parse
       └─ _call_groq_with_retry()      AsyncGroq + tenacity retries
       └─ _extract_json()              robust JSON extraction from model output
       └─ _filter_line_numbers()       nullify lines not in changed added-lines
    → _build_summary(findings)         local summary + verdict, no extra AI call
    → ReviewResult

No secrets (API keys, tokens) are ever logged.
"""
import json
import logging
import re
from collections import Counter

from groq import AsyncGroq
from groq import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
)
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.exceptions import AIProviderConfigError, AIReviewError
from app.schemas.pr_context import ChangedFile, PRContext
from app.schemas.review_result import ReviewFinding, ReviewResult, ReviewSummary
from app.services.ai_provider import AIReviewProvider

logger = logging.getLogger(__name__)

# ── Prompts ────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a senior software engineer performing a focused, precise code review.
Your output must be valid JSON — nothing else, no markdown, no explanation.

Core rules
----------
1. ONLY review code that is visible in the provided diff (lines starting with '+').
2. Report real issues only: security vulnerabilities, logic/edge-case bugs,
   performance problems, maintainability concerns, missing test coverage.
3. Flag style issues ONLY when they cause correctness or serious readability problems.
4. Set "line" to the exact NEW file line number of the problem, or null if uncertain.
5. Do NOT invent file names, function names, or line numbers.
6. Prefer 3 high-confidence findings over 10 speculative ones.
7. If nothing is genuinely wrong, return {"findings": []}.
8. confidence must be a float between 0.0 and 1.0.
"""

_USER_TEMPLATE = """\
Review the following pull request file change and return JSON.

Repository : {repository}
PR Title   : {title}
Author     : {author}
Base → Head: {base_branch} → {head_branch}

File       : {filename}
Status     : {status}  (+{additions} additions / -{deletions} deletions)

Diff:
{patch}

Return exactly this JSON structure (no extra keys, no prose):
{{
  "findings": [
    {{
      "file_path": "{filename}",
      "line": <integer line number in new file, or null>,
      "severity": "<low|medium|high|critical>",
      "category": "<security|logic_bug|performance|maintainability|test_coverage|style>",
      "title": "<concise title>",
      "description": "<what the problem is and why it matters>",
      "suggestion": "<concrete fix or improvement>",
      "confidence": <0.0-1.0>
    }}
  ]
}}
"""

# ── Constants ──────────────────────────────────────────────────────────────────

_TRUNCATION_MARKER = "\n\n... [diff truncated — remaining lines omitted] ..."
_RETRYABLE_EXCEPTIONS = (RateLimitError, APIConnectionError, InternalServerError)


# ── Provider ───────────────────────────────────────────────────────────────────

class GroqReviewProvider(AIReviewProvider):
    """Groq-backed implementation of the AI review provider."""

    def __init__(self) -> None:
        if not settings.GROQ_API_KEY:
            raise AIProviderConfigError(
                "GROQ_API_KEY is not set. Add it to backend/.env before running reviews."
            )
        # Client is reused across calls; API key is never logged.
        self._client = AsyncGroq(api_key=settings.GROQ_API_KEY)

    async def review_pr(self, ctx: PRContext) -> ReviewResult:
        reviewable, skipped = _partition_files(ctx)

        if not reviewable:
            logger.info("No reviewable files in PR %s#%d", ctx.metadata.repository_full_name, ctx.metadata.pr_number)

        all_findings: list[ReviewFinding] = []
        reviewed_files: list[str] = []

        for file in reviewable:
            try:
                findings = await self._review_file(ctx, file)
                all_findings.extend(findings)
                reviewed_files.append(file.filename)
                logger.info(
                    "Reviewed %s — %d finding(s)",
                    file.filename,
                    len(findings),
                )
            except (AIReviewError, BadRequestError, NotFoundError, AuthenticationError) as exc:
                # Non-retryable failures: note the file as skipped and continue.
                logger.warning("Skipping %s due to non-retryable error: %s", file.filename, exc)
                skipped.append(f"{file.filename} [review error: {type(exc).__name__}]")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Unexpected error reviewing %s: %s", file.filename, exc)
                skipped.append(f"{file.filename} [unexpected error]")

        # Apply global confidence filter (should_comment is already set by Pydantic validator,
        # but we still filter out low-confidence findings from the final result).
        confident = [f for f in all_findings if f.confidence >= settings.AI_MIN_CONFIDENCE]
        dropped = len(all_findings) - len(confident)
        if dropped:
            logger.debug("Filtered %d low-confidence finding(s) below %.2f", dropped, settings.AI_MIN_CONFIDENCE)

        summary = _build_summary(confident)

        return ReviewResult(
            delivery_id=ctx.delivery_id,
            repository=ctx.metadata.repository_full_name,
            pr_number=ctx.metadata.pr_number,
            provider=settings.AI_PROVIDER,
            model=settings.GROQ_MODEL,
            findings=confident,
            summary=summary,
            reviewed_files=reviewed_files,
            skipped_files=skipped,
        )

    async def _review_file(self, ctx: PRContext, file: ChangedFile) -> list[ReviewFinding]:
        """Review a single file and return its parsed findings."""
        patch = file.patch or ""
        if len(patch) > settings.AI_MAX_PATCH_CHARS_PER_FILE:
            patch = patch[: settings.AI_MAX_PATCH_CHARS_PER_FILE] + _TRUNCATION_MARKER

        user_msg = _build_user_message(ctx, file, patch)
        raw = await self._call_groq_with_retry(user_msg)

        data = _extract_json(raw)
        raw_findings: list[dict] = data.get("findings", [])

        added_lines = _extract_added_line_numbers(file.patch or "")
        return _parse_findings(raw_findings, file.filename, added_lines)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _call_groq_with_retry(self, user_message: str) -> str:
        """
        Single Groq chat completion call, wrapped with tenacity retries.

        Retried on: RateLimitError, APIConnectionError, InternalServerError.
        NOT retried on: AuthenticationError, BadRequestError, NotFoundError
        (those indicate configuration problems, not transient failures).
        """
        try:
            response = await self._client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,       # low for deterministic, focused analysis
                max_tokens=2048,
                response_format={"type": "json_object"},
            )
        except NotFoundError as exc:
            raise AIProviderConfigError(
                f"Model '{settings.GROQ_MODEL}' was not found on Groq. "
                f"Set GROQ_MODEL to a supported model (e.g. llama-3.3-70b-versatile)."
            ) from exc
        except AuthenticationError as exc:
            raise AIProviderConfigError(
                "Groq API authentication failed — check GROQ_API_KEY."
            ) from exc

        content = response.choices[0].message.content or "{}"
        return content


# ── Helpers ────────────────────────────────────────────────────────────────────

def _partition_files(ctx: PRContext) -> tuple[list[ChangedFile], list[str]]:
    """Split changed files into reviewable and skipped lists."""
    reviewable: list[ChangedFile] = []
    skipped: list[str] = []

    for f in ctx.changed_files:
        if f.is_binary:
            skipped.append(f"{f.filename} [binary]")
        elif not f.patch:
            skipped.append(f"{f.filename} [no patch]")
        else:
            reviewable.append(f)

    if len(reviewable) > settings.AI_MAX_FILES:
        over = reviewable[settings.AI_MAX_FILES :]
        reviewable = reviewable[: settings.AI_MAX_FILES]
        for f in over:
            skipped.append(f"{f.filename} [AI_MAX_FILES limit]")

    return reviewable, skipped


def _build_user_message(ctx: PRContext, file: ChangedFile, patch: str) -> str:
    m = ctx.metadata
    return _USER_TEMPLATE.format(
        repository=m.repository_full_name,
        title=m.title,
        author=m.author,
        base_branch=m.base_branch,
        head_branch=m.head_branch,
        filename=file.filename,
        status=file.status,
        additions=file.additions,
        deletions=file.deletions,
        patch=patch,
    )


def _extract_json(text: str) -> dict:
    """
    Robustly extract a JSON object from model output.

    Priority:
      1. Direct json.loads (works when response_format=json_object is respected)
      2. JSON inside a markdown ```json ... ``` fence
      3. First { ... } block found in the text
      4. Empty findings fallback
    """
    text = text.strip()

    # Attempt 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt 2: strip markdown fences
    for pattern in (r"```json\s*(.*?)\s*```", r"```\s*(.*?)\s*```"):
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue

    # Attempt 3: find outermost JSON object
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning("Could not extract JSON from model output (first 200 chars): %s", text[:200])
    return {"findings": []}


def _parse_findings(
    raw: list[dict],
    default_filename: str,
    added_lines: set[int],
) -> list[ReviewFinding]:
    """
    Convert raw model dicts into validated ReviewFinding objects.

    - Silently skips malformed entries (logs at DEBUG level).
    - Nullifies line numbers that are not in the diff's added lines
      (GitHub can only comment on changed lines).
    """
    results: list[ReviewFinding] = []

    for entry in raw:
        try:
            finding = ReviewFinding(
                file_path=entry.get("file_path") or default_filename,
                line=_safe_int(entry.get("line")),
                severity=entry.get("severity", "low"),
                category=entry.get("category", "maintainability"),
                title=str(entry.get("title", ""))[:200],
                description=str(entry.get("description", "")),
                suggestion=str(entry.get("suggestion", "")),
                confidence=float(entry.get("confidence", 0.5)),
                should_comment=False,  # validator will compute the correct value
            )
            # Nullify line if it falls outside the added-line set — we can't
            # post an inline comment there in Phase 6.
            if finding.line is not None and added_lines and finding.line not in added_lines:
                finding = finding.model_copy(update={"line": None})

            results.append(finding)

        except Exception as exc:  # noqa: BLE001
            logger.debug("Skipping malformed finding from model output: %s — %s", entry, exc)

    return results


def _safe_int(value: object) -> int | None:
    """Return int(value) or None, never raising."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_added_line_numbers(patch: str) -> set[int]:
    """
    Parse a unified diff patch and return the set of line numbers (in the new
    file) that were added (`+` lines).

    These are the only lines that GitHub allows inline comments on.

    Hunk header format: @@ -old_start[,old_count] +new_start[,new_count] @@
    """
    added: set[int] = set()
    current_new = 0

    for line in patch.splitlines():
        if line.startswith("@@"):
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if m:
                current_new = int(m.group(1)) - 1  # pre-decrement: first real line will become new_start
        elif line.startswith("+++") or line.startswith("---") or line.startswith("\\"):
            continue  # file-header and "no newline" markers
        elif line.startswith("+"):
            current_new += 1
            added.add(current_new)
        elif line.startswith("-"):
            pass  # removed lines don't advance the new-file counter
        else:
            current_new += 1  # context line (space prefix)

    return added


def _build_summary(findings: list[ReviewFinding]) -> ReviewSummary:
    """
    Derive a ReviewSummary entirely from the findings list — no extra AI call.

    Scoring
    -------
    critical → +35   high → +20   medium → +10   low → +3   (capped at 100)

    Risk level   Score range
    -----------  -----------
    low          0 – 15
    medium       16 – 45
    high         46 – 75
    critical     76 – 100

    Verdict
    -------
    critical or high present  → request_changes
    medium only               → comment
    low only / nothing        → approve
    """
    counts: Counter[str] = Counter(f.severity for f in findings)

    critical = counts["critical"]
    high = counts["high"]
    medium = counts["medium"]
    low = counts["low"]
    total = len(findings)

    score = min(100, critical * 35 + high * 20 + medium * 10 + low * 3)

    if score <= 15:
        risk_level = "low"
    elif score <= 45:
        risk_level = "medium"
    elif score <= 75:
        risk_level = "high"
    else:
        risk_level = "critical"

    if critical > 0 or high > 0:
        verdict = "request_changes"
    elif medium > 0:
        verdict = "comment"
    else:
        verdict = "approve"

    if total == 0:
        summary_text = "No significant issues found in the reviewed files. The PR looks clean."
    else:
        parts: list[str] = []
        if critical:
            parts.append(f"{critical} critical")
        if high:
            parts.append(f"{high} high")
        if medium:
            parts.append(f"{medium} medium")
        if low:
            parts.append(f"{low} low")
        label = "finding" if total == 1 else "findings"
        summary_text = f"Found {total} {label} across reviewed files: {', '.join(parts)}."

    return ReviewSummary(
        verdict=verdict,
        risk_level=risk_level,
        severity_score=score,
        summary_text=summary_text,
        total_findings=total,
        critical_count=critical,
        high_count=high,
        medium_count=medium,
        low_count=low,
    )
