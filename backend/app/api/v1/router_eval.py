from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.api.deps import get_current_user
from app.models.user import User
from app.services.router.model_router import model_router

router = APIRouter(prefix="/router", tags=["Router"])


class RouteEvalRequest(BaseModel):
    prompt: str
    requested_model_id: Optional[str] = "nexora-auto"


@router.post("/evaluate", response_model=Dict[str, Any])
async def evaluate_routing(
    data: RouteEvalRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Evaluate the Intelligent Model Router on a sample prompt.
    Returns task intent, complexity, capability requirements, and chosen model.
    """
    decision = model_router.route(
        requested_model_id=data.requested_model_id,
        prompt=data.prompt
    )
    return {
        "selected_model_id": decision.selected_model_id,
        "provider": decision.provider,
        "reason": decision.reason,
        "confidence": decision.confidence,
        "is_override": decision.is_override,
        "task_profile": decision.task_profile.model_dump()
    }

