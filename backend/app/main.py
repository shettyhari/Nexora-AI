from contextlib import asynccontextmanager
import logging
import os
import time
from typing import Dict
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import select

from app.api.v1.inference import openai_router
from app.api.v1.models import DEFAULT_MODELS
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, Base, cache, engine
from app.models.ecosystem import PublishedModel
from app.models.lab import LabCheckpoint
from app.models.model_config import ModelConfiguration
from app.services.billing_service import billing_service
from app.services.model_registry.registry import model_registry

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("nexora")

# Lightweight process-level Prometheus telemetry counters
_PROCESS_START_TIME = time.time()
_METRICS: Dict[str, float] = {
    "http_requests_total": 0,
    "http_errors_total": 0,
    "http_latency_ms_sum": 0.0,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: database initialization, plan & catalog sync, and cleanup."""
    logger.info("Initializing NEXORA AI Backend services...")
    settings.validate_production_secrets()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.BACKUP_DIR, exist_ok=True)

    # Auto-create tables if running in SQLite / quickstart mode
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # 1. Seed model configurations if empty
        result = await session.execute(select(ModelConfiguration))
        if not result.scalars().all():
            logger.info("Seeding default model catalog...")
            for m_data in DEFAULT_MODELS:
                session.add(
                    ModelConfiguration(
                        id=m_data["id"],
                        model_key=m_data["model_key"],
                        display_name=m_data["display_name"],
                        provider=m_data["provider"],
                        model_name=m_data["model_name"],
                        context_window=m_data["context_window"],
                        max_tokens=m_data["max_tokens"],
                        supports_vision=m_data["supports_vision"],
                        supports_reasoning=m_data["supports_reasoning"],
                        is_enabled=m_data["is_enabled"],
                        is_default=m_data["is_default"],
                        badge=m_data.get("badge"),
                        description=m_data.get("description"),
                    )
                )

        # 2. Seed Free/Pro/Enterprise commercial subscription plans
        await billing_service.ensure_default_plans(session)

        # 3. Synchronize approved PublishedModel catalog & checkpoints into active ModelRegistry
        pub_res = await session.execute(select(PublishedModel))
        pub_rows = list(pub_res.scalars().all())
        if pub_rows:
            ckpt_ids = [r.checkpoint_id for r in pub_rows if r.checkpoint_id]
            ckpt_paths: Dict[str, str] = {}
            if ckpt_ids:
                c_res = await session.execute(select(LabCheckpoint).where(LabCheckpoint.id.in_(ckpt_ids)))
                for c in c_res.scalars().all():
                    ckpt_paths[c.id] = c.storage_path
            model_registry.sync_published_models(pub_rows, ckpt_paths)

        await session.commit()

    await cache.init()
    logger.info("NEXORA AI Backend started successfully.")

    yield

    await cache.close()
    await engine.dispose()
    logger.info("NEXORA AI Backend shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-grade Independent Commercial AI Platform & Research Ecosystem API",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)


@app.middleware("http")
async def security_headers_and_metrics_middleware(request: Request, call_next):
    t0 = time.perf_counter()
    response: Response = await call_next(request)
    dt_ms = (time.perf_counter() - t0) * 1000.0

    _METRICS["http_requests_total"] += 1
    _METRICS["http_latency_ms_sum"] += dt_ms
    if response.status_code >= 400:
        _METRICS["http_errors_total"] += 1

    # Hardened HTTP security headers
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(self), geolocation=()")
    if settings.ENVIRONMENT.lower() == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health_check():
    """Service health and readiness check."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": round(time.time() - _PROCESS_START_TIME, 2),
    }


@app.get("/metrics", tags=["Observability"], response_class=PlainTextResponse)
async def prometheus_metrics():
    """Prometheus text-exposition metrics endpoint for scraping."""
    reqs = int(_METRICS["http_requests_total"])
    errs = int(_METRICS["http_errors_total"])
    avg_lat = round(_METRICS["http_latency_ms_sum"] / max(1, reqs), 3)
    uptime = round(time.time() - _PROCESS_START_TIME, 2)
    active_models = len(model_registry.list_models(include_inactive=False))

    lines = [
        "# HELP nexora_http_requests_total Total HTTP requests processed by NEXORA backend.",
        "# TYPE nexora_http_requests_total counter",
        f"nexora_http_requests_total {reqs}",
        "# HELP nexora_http_errors_total Total HTTP 4xx/5xx responses.",
        "# TYPE nexora_http_errors_total counter",
        f"nexora_http_errors_total {errs}",
        "# HELP nexora_http_avg_latency_ms Mean HTTP request latency in milliseconds.",
        "# TYPE nexora_http_avg_latency_ms gauge",
        f"nexora_http_avg_latency_ms {avg_lat}",
        "# HELP nexora_models_registered Active models in ModelRegistry.",
        "# TYPE nexora_models_registered gauge",
        f"nexora_models_registered {active_models}",
        "# HELP nexora_process_uptime_seconds Process uptime in seconds.",
        "# TYPE nexora_process_uptime_seconds gauge",
        f"nexora_process_uptime_seconds {uptime}",
    ]
    return "\n".join(lines) + "\n"


# Include API v1 router & root OpenAI-compatible inference router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(openai_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."},
    )
