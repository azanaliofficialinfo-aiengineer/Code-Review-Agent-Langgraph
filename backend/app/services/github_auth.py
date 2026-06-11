"""
GitHub App authentication.

Two-step flow
-------------
1. create_github_app_jwt()           — signs a short-lived RS256 JWT with the App
                                       private key; identifies the App itself.
2. get_installation_access_token()   — exchanges the JWT for a per-installation
                                       bearer token; used for all subsequent API calls.

Neither token value is ever logged.
"""
import logging
import time

import httpx
import jwt

from app.core.config import settings
from app.core.exceptions import GitHubAPIError, GitHubAuthError

logger = logging.getLogger(__name__)

_GITHUB_API_BASE = "https://api.github.com"
_GITHUB_ACCEPT   = "application/vnd.github+json"
_GITHUB_VERSION  = "2022-11-28"

# GitHub allows up to 10 minutes; use full window so we don't race on expiry.
_JWT_EXPIRY_SECONDS = 600
# Issue slightly in the past to tolerate server clock skew.
_JWT_ISSUED_SKEW = 60


def _normalize_private_key(raw: str) -> str:
    """
    Ensure a PEM key stored in .env is usable by the JWT library.

    .env files commonly store multi-line values with literal "\\n" escape
    sequences instead of real newlines.  Both forms are normalised here.
    """
    stripped = raw.strip()
    # Only replace when there are literal backslash-n sequences AND no real newlines —
    # avoids double-processing keys that already have proper line breaks.
    if "\\n" in stripped and "\n" not in stripped:
        stripped = stripped.replace("\\n", "\n")
    return stripped


def create_github_app_jwt() -> str:
    """
    Build and sign a short-lived RS256 JWT for the GitHub App identity.

    Raises:
        GitHubAuthError: If required settings are missing or the key is invalid.
    """
    if not settings.GITHUB_APP_ID or not settings.GITHUB_PRIVATE_KEY:
        raise GitHubAuthError(
            "GITHUB_APP_ID and GITHUB_PRIVATE_KEY must be set before making GitHub API calls."
        )

    now = int(time.time())
    private_key = _normalize_private_key(settings.GITHUB_PRIVATE_KEY)

    payload = {
        "iat": now - _JWT_ISSUED_SKEW,          # tolerate clock drift
        "exp": now + _JWT_EXPIRY_SECONDS,
        "iss": settings.GITHUB_APP_ID,           # App ID as string (GitHub requirement)
    }

    try:
        token: str = jwt.encode(payload, private_key, algorithm="RS256")
    except Exception as exc:
        raise GitHubAuthError(f"Failed to sign GitHub App JWT: {exc}") from exc

    logger.debug("Generated GitHub App JWT (iss=%s, exp +%ds)", settings.GITHUB_APP_ID, _JWT_EXPIRY_SECONDS)
    return token


async def get_installation_access_token(installation_id: int) -> str:
    """
    Exchange a GitHub App JWT for a per-installation bearer token.

    The returned token is valid for ~1 hour and must not be logged or stored
    in plain text.

    Raises:
        GitHubAuthError:  JWT creation failed.
        GitHubAPIError:   GitHub API returned a non-2xx status.
    """
    app_jwt = create_github_app_jwt()
    url = f"{_GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": _GITHUB_ACCEPT,
                "X-GitHub-Api-Version": _GITHUB_VERSION,
            },
        )

    if not response.is_success:
        msg = _extract_message(response)
        raise GitHubAPIError(response.status_code, msg, url)

    token: str = response.json()["token"]
    logger.info("Obtained installation access token for installation_id=%d", installation_id)
    # Token value deliberately omitted from logs.
    return token


def _extract_message(response: httpx.Response) -> str:
    """Pull the human-readable message out of a GitHub error response."""
    try:
        return response.json().get("message", response.text[:300])
    except Exception:
        return response.text[:300]
