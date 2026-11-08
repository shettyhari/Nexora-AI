import asyncio
import logging
from typing import AsyncGenerator, Dict, List, Optional, Union
from app.core.config import settings
from app.services.llm.base import (
    BaseLLMProvider,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    ProviderHealth,
)
from app.services.llm.gemini import GeminiProvider
from app.services.llm.openai_provider import OpenAIProvider
from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.huggingface_provider import HuggingFaceProvider
from app.services.llm.openai_compatible_provider import OpenAICompatibleProvider
from app.services.llm.nexora_provider import NexoraProvider
from app.services.model_registry.registry import ModelProvider, model_registry

logger = logging.getLogger(__name__)


class UnifiedModelGateway:
    """Unified LLM Gateway providing provider routing, health checks, resilience, and metrics."""

    def __init__(self):
        self._providers: Dict[str, BaseLLMProvider] = {
            ModelProvider.GOOGLE: GeminiProvider(),
            ModelProvider.OPENAI: OpenAIProvider(),
            ModelProvider.ANTHROPIC: AnthropicProvider(),
            ModelProvider.HUGGINGFACE: HuggingFaceProvider(),
            ModelProvider.OPENAI_COMPATIBLE: OpenAICompatibleProvider(),
            ModelProvider.NEXORA: NexoraProvider(),
        }
        self._fallback_provider = self._providers[ModelProvider.NEXORA]

    def get_provider(self, provider_type: Union[ModelProvider, str]) -> BaseLLMProvider:
        key = str(provider_type).lower()
        return self._providers.get(key, self._fallback_provider)

    def resolve_provider_for_model(self, model_id: str) -> BaseLLMProvider:
        desc = model_registry.get_model(model_id)
        if desc:
            provider = self.get_provider(desc.provider)
            if provider.is_configured():
                return provider
            # If specified provider is not configured, fallback gracefully
            logger.info(f"Provider '{desc.provider}' for model '{model_id}' is not configured. Using NEXORA fallback.")
            return self._fallback_provider

        # Unknown model -> fallback
        return self._fallback_provider

    async def stream(self, request: LLMRequest) -> AsyncGenerator[LLMStreamChunk, None]:
        """Stream chunks from the resolved provider with fallback on failure."""
        provider = self.resolve_provider_for_model(request.model)

        # Attempt primary provider streaming
        has_yielded_token = False
        saw_error = False
        error_msg = ""

        try:
            async for chunk in provider.stream_chat(request):
                if chunk.type == "error":
                    saw_error = True
                    error_msg = chunk.content
                    break
                if chunk.type in ["token", "reasoning"]:
                    has_yielded_token = True
                yield chunk

        except Exception as e:
            saw_error = True
            error_msg = str(e)

        # If primary failed before emitting tokens, fallback gracefully
        if saw_error and not has_yielded_token:
            logger.warning(f"Provider failed with '{error_msg}'. Triggering NEXORA neural fallback.")
            yield LLMStreamChunk(
                type="token",
                content=f"> *[Notice: System routed through NEXORA resilience gateway due to upstream notification: {error_msg}]*\n\n",
                resolved_model="nexora-flagship"
            )
            async for chunk in self._fallback_provider.stream_chat(request):
                yield chunk

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Non-streaming generation with fallback."""
        provider = self.resolve_provider_for_model(request.model)
        try:
            return await provider.generate(request)
        except Exception as e:
            logger.warning(f"Generate failed on primary provider: {e}. Using fallback.")
            return await self._fallback_provider.generate(request)

    async def check_all_health(self) -> Dict[str, ProviderHealth]:
        """Ping all configured providers concurrently."""
        results: Dict[str, ProviderHealth] = {}
        tasks = []
        keys = list(self._providers.keys())

        for key in keys:
            tasks.append(self._providers[key].health_check())

        health_reports = await asyncio.gather(*tasks, return_exceptions=True)
        for key, report in zip(keys, health_reports):
            if isinstance(report, ProviderHealth):
                results[key] = report
            else:
                results[key] = ProviderHealth(
                    provider=key,
                    status="offline",
                    error=str(report)
                )

        return results


# Global singleton gateway
gateway = UnifiedModelGateway()
llm_gateway = gateway


