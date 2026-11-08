from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models.user import User
from app.services.research.research_service import web_research_service

router = APIRouter(prefix="/research", tags=["Web Research Agent"])


class SearchRequest(BaseModel):
    query: str
    max_results: int = 5


class ScrapeRequest(BaseModel):
    url: str
    timeout_seconds: float = 10.0


class ReportRequest(BaseModel):
    query: str
    max_sources: int = 4


@router.post("/search")
async def search_web(
    req: SearchRequest,
    current_user: User = Depends(get_current_user)
):
    """Search the web for real-time sources."""
    results = await web_research_service.search_web(req.query, max_results=req.max_results)
    return {
        "success": True,
        "query": req.query,
        "results": [r.dict() for r in results]
    }


@router.post("/scrape")
async def scrape_web_page(
    req: ScrapeRequest,
    current_user: User = Depends(get_current_user)
):
    """Safely fetch and sanitize a web page with strict SSRF defense."""
    data = await web_research_service.fetch_page(req.url, timeout_seconds=req.timeout_seconds)
    if not data.get("success"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=data.get("error", "Failed to retrieve page."))
    return {
        "success": True,
        "data": data
    }


@router.post("/report")
async def generate_research_report(
    req: ReportRequest,
    current_user: User = Depends(get_current_user)
):
    """Synthesize multi-source research report with verified non-fabricated citations."""
    report = await web_research_service.conduct_research(req.query, max_sources=req.max_sources)
    return {
        "success": True,
        "report": report.dict()
    }
