import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analytics import router as analytics_router
from app.api.debug import router as debug_router
from app.api.health import router as health_router
from app.api.repositories import router as repositories_router
from app.api.reviews import router as reviews_router
from app.api.webhooks import router as webhooks_router
from app.core.config import settings
from app.db.session import engine
from app.services.redis_service import close_redis_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def _build_cors_origins() -> list[str]:
    """
    Resolve the allowed CORS origins list.

    - Development/staging: always includes localhost:3000 and 127.0.0.1:3000
      regardless of BACKEND_CORS_ORIGINS so dev works out of the box.
    - Production: requires BACKEND_CORS_ORIGINS to be explicitly configured;
      raises RuntimeError at startup if it is empty.

    Never allows allow_origins=["*"] together with allow_credentials=True —
    that combination is invalid per the CORS spec and rejected by browsers.
    """
    origins = list(settings.BACKEND_CORS_ORIGINS)

    if settings.ENVIRONMENT == "production":
        if not origins:
            raise RuntimeError(
                "BACKEND_CORS_ORIGINS must be set in production. "
                "Example: BACKEND_CORS_ORIGINS=https://myapp.railway.app\n"
                "Set this environment variable before starting the server."
            )
        return origins

    # Development / staging: ensure localhost variants are always present.
    dev_defaults = {
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    }
    return sorted(set(origins) | dev_defaults)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting %s (%s)", settings.APP_NAME, settings.ENVIRONMENT)
    yield
    # Graceful shutdown: close Redis connection pool.
    await close_redis_client()
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    description="Autonomous AI-powered GitHub PR reviewer",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_build_cors_origins(),
    allow_credentials=settings.ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

app.include_router(health_router, tags=["health"])
app.include_router(webhooks_router, tags=["webhooks"])
app.include_router(reviews_router, tags=["reviews"])
app.include_router(repositories_router, tags=["repositories"])
app.include_router(analytics_router, tags=["analytics"])

# Debug router is available in development and staging only.
if settings.ENVIRONMENT != "production":
    app.include_router(debug_router)


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
    }
