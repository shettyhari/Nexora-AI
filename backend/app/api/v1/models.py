from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.model_config import ModelConfiguration
from app.models.user import User
from app.schemas.model_config import ModelConfigResponse

router = APIRouter(prefix="/models", tags=["Models"])

# Default seeded model catalog
DEFAULT_MODELS = [
    {
        "id": "model_nexora_pro",
        "model_key": "nexora-pro",
        "display_name": "NEXORA Pro 2.5",
        "provider": "gemini",
        "model_name": "gemini-1.5-pro",
        "context_window": 1000000,
        "max_tokens": 8192,
        "supports_vision": True,
        "supports_reasoning": True,
        "is_enabled": True,
        "is_default": True,
        "badge": "Flagship",
        "description": "Most intelligent general model for complex tasks, deep coding, and multimodal synthesis."
    },
    {
        "id": "model_nexora_flash",
        "model_key": "nexora-flash",
        "display_name": "NEXORA Flash 2.5",
        "provider": "gemini",
        "model_name": "gemini-1.5-flash",
        "context_window": 1000000,
        "max_tokens": 8192,
        "supports_vision": True,
        "supports_reasoning": False,
        "is_enabled": True,
        "is_default": False,
        "badge": "Fast",
        "description": "Ultra-fast response latency with expansive context window for rapid everyday tasks."
    },
    {
        "id": "model_gpt4o",
        "model_key": "gpt-4o",
        "display_name": "GPT-4o Omnimodal",
        "provider": "openai",
        "model_name": "gpt-4o",
        "context_window": 128000,
        "max_tokens": 4096,
        "supports_vision": True,
        "supports_reasoning": True,
        "is_enabled": True,
        "is_default": False,
        "badge": "OpenAI",
        "description": "High-intelligence flagship model with cross-domain reasoning and vision capabilities."
    },
    {
        "id": "model_claude35",
        "model_key": "claude-3-5-sonnet",
        "display_name": "Claude 3.5 Sonnet",
        "provider": "anthropic",
        "model_name": "claude-3-5-sonnet-20241022",
        "context_window": 200000,
        "max_tokens": 8192,
        "supports_vision": True,
        "supports_reasoning": True,
        "is_enabled": True,
        "is_default": False,
        "badge": "Anthropic",
        "description": "Leading standard for code generation, nuanced reasoning, and architectural design."
    }
]


@router.get("", response_model=List[ModelConfigResponse])
async def list_available_models(
    db: AsyncSession = Depends(get_db)
):
    """List available AI models in the NEXORA catalog."""
    query = select(ModelConfiguration).where(ModelConfiguration.is_enabled == True)
    result = await db.execute(query)
    models = result.scalars().all()

    if not models:
        # Return default preset catalog
        return [ModelConfigResponse(**m) for m in DEFAULT_MODELS]

    return models
