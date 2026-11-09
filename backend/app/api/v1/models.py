from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.ecosystem import PublishedModel
from app.models.lab import LabCheckpoint
from app.models.user import User
from app.services.billing_service import billing_service
from app.services.model_registry.registry import model_registry

router = APIRouter(prefix="/models", tags=["Models"])

DEFAULT_MODELS = [
    {
        "id": m.id,
        "model_key": m.id,
        "display_name": m.name,
        "provider": m.provider.value,
        "model_name": m.id,
        "context_window": m.context_window,
        "max_tokens": m.max_output_tokens,
        "supports_vision": m.capabilities.vision,
        "supports_reasoning": m.capabilities.reasoning,
        "is_enabled": True,
        "is_default": m.is_default,
        "badge": "Auto" if m.id == "nexora-auto" else ("Flagship" if "flagship" in m.id else m.provider.value.capitalize()),
        "description": m.description,
    }
    for m in model_registry.list_models()
]


@router.get("", response_model=List[Dict[str, Any]])
async def list_models(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all active models dynamically from ModelRegistry & PublishedModel catalog."""
    pub_res = await db.execute(select(PublishedModel))
    pub_rows = list(pub_res.scalars().all())
    if pub_rows:
        ckpt_ids = [r.checkpoint_id for r in pub_rows if r.checkpoint_id]
        ckpt_paths: Dict[str, str] = {}
        if ckpt_ids:
            c_res = await db.execute(select(LabCheckpoint).where(LabCheckpoint.id.in_(ckpt_ids)))
            for c in c_res.scalars().all():
                ckpt_paths[c.id] = c.storage_path
        model_registry.sync_published_models(pub_rows, ckpt_paths)

    _, plan = await billing_service.get_or_create_subscription(db, current_user.id)
    models = model_registry.list_models(include_inactive=False)
    output = []
    for m in models:
        permitted, _ = billing_service.check_model_permitted(
            plan, current_user.role, m.id, m.min_plan_tier
        )
        output.append(
            {
                "id": m.id,
                "model_key": m.id,
                "display_name": m.name,
                "name": m.name,
                "provider": m.provider.value,
                "version": m.version,
                "description": m.description,
                "context_window": m.context_window,
                "max_tokens": m.max_output_tokens,
                "supports_vision": m.capabilities.vision,
                "supports_reasoning": m.capabilities.reasoning,
                "supports_tools": m.capabilities.function_calling,
                "is_default": m.is_default,
                "is_enabled": True,
                "is_proprietary": m.is_proprietary,
                "min_plan_tier": m.min_plan_tier,
                "plan_permitted": permitted,
                "pricing": {
                    "input_per_million": m.pricing.input_per_million,
                    "output_per_million": m.pricing.output_per_million,
                },
                "deployment": m.deployment.value,
                "status": m.status.value,
                "recommended_intents": m.recommended_intents,
            }
        )
    return output


@router.get("/{model_id}", response_model=Dict[str, Any])
async def get_model_details(
    model_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get complete metadata, capabilities, and pricing for a specific model."""
    desc = model_registry.get_model(model_id)
    if not desc:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found in registry")

    return {
        "id": desc.id,
        "name": desc.name,
        "provider": desc.provider.value,
        "version": desc.version,
        "description": desc.description,
        "capabilities": desc.capabilities.model_dump(),
        "context_window": desc.context_window,
        "max_output_tokens": desc.max_output_tokens,
        "supported_modalities": desc.supported_modalities,
        "pricing": desc.pricing.model_dump(),
        "deployment": desc.deployment.value,
        "status": desc.status.value,
        "is_default": desc.is_default,
        "is_proprietary": desc.is_proprietary,
        "min_plan_tier": desc.min_plan_tier,
        "recommended_intents": desc.recommended_intents,
    }
