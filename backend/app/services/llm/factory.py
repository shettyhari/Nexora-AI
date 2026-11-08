import asyncio
import logging
from typing import AsyncGenerator, List, Optional, Union
from app.core.config import settings
from app.services.llm.base import (
    BaseLLMProvider,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    LLMUsage,
    ProviderHealth,
)
from app.services.llm.gemini import GeminiProvider
from app.services.llm.openai_provider import OpenAIProvider
from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.huggingface_provider import HuggingFaceProvider
from app.services.llm.openai_compatible_provider import OpenAICompatibleProvider
from app.services.llm.nexora_provider import NexoraProvider

logger = logging.getLogger(__name__)


class LocalFallbackProvider(NexoraProvider):
    """
    Backward-compatible fallback provider for local development without API keys.
    Delivers rich Markdown, code snippets, LaTeX math, and reasoning blocks.
    """
    pass


class LLMFactory:
    """Factory for selecting and instantiating LLM providers."""

    @staticmethod
    def get_provider(model: Optional[str] = None) -> BaseLLMProvider:
        from app.services.llm.gateway import gateway
        if not model:
            model = settings.DEFAULT_MODEL_ID
        return gateway.resolve_provider_for_model(model)
