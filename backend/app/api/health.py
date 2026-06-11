import logging

from fastapi import APIRouter

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", summary="Liveness probe")
async def health_check():
    """Returns 200 while the process is alive — used by Docker and load balancers."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "version": "0.1.0",
    }


@router.get("/health/ready", summary="Readiness probe")
async def readiness_check():
    """
    Returns 200 only when all critical dependencies are reachable.
    Database check is stubbed until Phase 7 introduces ORM models.
    """
    from app.services.redis_service import ping_redis  # local import avoids circular dep at module load

    redis_ok = await ping_redis()

    checks = {
        "redis": "ok" if redis_ok else "unavailable",
        "database": "not_configured",  # wired in Phase 7
    }

    # Degraded if any *active* dependency is unhealthy.
    # "not_configured" counts as neutral (not yet enabled).
    active_failures = [k for k, v in checks.items() if v == "unavailable"]
    status = "ready" if not active_failures else "degraded"

    if active_failures:
        logger.warning("Readiness check degraded: %s", active_failures)

    return {"status": status, "checks": checks}
