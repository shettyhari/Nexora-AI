from contextlib import asynccontextmanager
import logging
import os
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.v1.models import DEFAULT_MODELS
from app.api.v1.inference import openai_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, Base, cache, engine
from app.models.model_config import ModelConfiguration

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("nexora")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: database initialization and cleanup."""
    logger.info("Initializing NEXORA AI Backend services...")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # Auto-create tables if running in SQLite / quickstart mode
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed model configurations if empty
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ModelConfiguration))
        existing_models = result.scalars().all()
        if not existing_models:
            logger.info("Seeding default model catalog...")
            for m_data in DEFAULT_MODELS:
                model_cfg = ModelConfiguration(
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
                    description=m_data.get("description")
                )
                session.add(model_cfg)
            await session.commit()

    # Initialize cache
    await cache.init()
    logger.info("NEXORA AI Backend started successfully.")

    yield

    # Cleanup
    await cache.close()
    await engine.dispose()
    logger.info("NEXORA AI Backend shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-grade AI Chat Application Backend API",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

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
        "environment": "development" if settings.DEBUG else "production"
    }


# Include API v1 router & root OpenAI-compatible inference router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(openai_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."}
    )

