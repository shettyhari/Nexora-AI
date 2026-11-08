"""
Entrypoint for Vercel Serverless / ASGI runners.
Exposes the FastAPI application instance from app.main.
"""
from app.main import app

__all__ = ["app"]

