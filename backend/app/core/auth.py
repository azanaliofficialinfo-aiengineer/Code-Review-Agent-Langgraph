"""
API bearer-token authentication dependency.

Usage — apply to a whole router:
    router = APIRouter(dependencies=[Depends(require_api_auth)])

Protected routes require:
    Authorization: Bearer <API_AUTH_TOKEN>

Auth is always enforced when ENVIRONMENT == "production".
In other environments it is enforced when API_AUTH_ENABLED == true.
When API_AUTH_ENABLED is false (development default) all requests pass.
"""
import secrets

from fastapi import Header, HTTPException

from app.core.config import settings


async def require_api_auth(
    authorization: str | None = Header(None, alias="Authorization"),
) -> None:
    """
    FastAPI dependency that enforces bearer-token auth.

    No-op when auth is disabled (development default).
    Raises HTTP 401 on missing or invalid credentials.
    Raises HTTP 503 if auth is enabled but the token is not configured.
    """
    is_enabled = settings.API_AUTH_ENABLED or (settings.ENVIRONMENT == "production")

    if not is_enabled:
        return

    if not settings.API_AUTH_TOKEN:
        raise HTTPException(
            status_code=503,
            detail=(
                "API authentication is enabled but API_AUTH_TOKEN is not configured. "
                "Set API_AUTH_TOKEN in the environment."
            ),
        )

    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provided = authorization[7:]  # strip "Bearer " prefix

    # Timing-safe comparison prevents token enumeration via timing attacks.
    if not secrets.compare_digest(
        provided.encode("utf-8"),
        settings.API_AUTH_TOKEN.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
