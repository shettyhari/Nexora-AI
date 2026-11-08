from typing import Any, Dict
from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.models.user import User
from app.services.llm.gateway import gateway

router = APIRouter(prefix="/gateway", tags=["Gateway"])


@router.get("/health", response_model=Dict[str, Any])
async def check_gateway_health(
    current_user: User = Depends(get_current_user)
):
    """
    Check real-time health, latency, and status across all integrated LLM providers:
    Google Gemini, OpenAI, Anthropic Claude, Hugging Face, OpenAI-compatible, and NEXORA.
    """
    health_reports = await gateway.check_all_health()
    return {
        provider_name: report.model_dump()
        for provider_name, report in health_reports.items()
    }
