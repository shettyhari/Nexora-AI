import asyncio
import logging
from typing import AsyncGenerator, Dict, Optional, Tuple, Union
from app.services.llm.base import (
    BaseLLMProvider,
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
    """
    Unified LLM Gateway providing provider routing, health checks, resilience,
    cost accounting, and STRICT attribution integrity (never silently mislabels fallbacks).
    """

    def __init__(self):
        self._providers: Dict[str, BaseLLMProvider] = {
            ModelProvider.GOOGLE.value: GeminiProvider(),
            ModelProvider.OPENAI.value: OpenAIProvider(),
            ModelProvider.ANTHROPIC.value: AnthropicProvider(),
            ModelProvider.HUGGINGFACE.value: HuggingFaceProvider(),
            ModelProvider.OPENAI_COMPATIBLE.value: OpenAICompatibleProvider(),
            ModelProvider.NEXORA.value: NexoraProvider(),
        }
        self._fallback_provider = self._providers[ModelProvider.NEXORA.value]

    def get_provider(self, provider_type: Union[ModelProvider, str]) -> BaseLLMProvider:
        raw = provider_type.value if isinstance(provider_type, ModelProvider) else str(provider_type)
        key = raw.lower()
        return self._providers.get(key, self._fallback_provider)

    def resolve_execution_target(self, model_id: str) -> Tuple[BaseLLMProvider, str, str, bool, Optional[str], Optional[str]]:
        """
        Resolve target execution provider and truthful identity metadata:
        Returns: (provider_instance, target_model_id, actual_provider_name, fallback_used, fallback_from_model, fallback_reason)
        """
        desc = model_registry.get_model(model_id)
        if desc:
            provider = self.get_provider(desc.provider)
            if provider.is_configured():
                return provider, desc.id, desc.provider.value, False, None, None

            reason = (
                f"Configured external provider '{desc.provider.value}' for '{desc.id}' lacks API credentials; "
                "routed transparently to NEXORA Flagship fallback."
            )
            logger.info(reason)
            return self._fallback_provider, "nexora-flagship", "nexora", True, desc.id, reason

        # Unknown model alias fallback
        reason = f"Requested model '{model_id}' not found in active catalog; routed transparently to NEXORA Flagship."
        return self._fallback_provider, "nexora-flagship", "nexora", True, model_id, reason

    def resolve_provider_for_model(self, model_id: str) -> BaseLLMProvider:
        provider, _, _, _, _, _ = self.resolve_execution_target(model_id)
        return provider

    async def stream(self, request: LLMRequest) -> AsyncGenerator[LLMStreamChunk, None]:
        """Stream chunks from the resolved provider with transparent fallback attribution."""
        provider, target_model, actual_provider, pre_fallback, fallback_from, fallback_reason = (
            self.resolve_execution_target(request.model)
        )

        effective_req = request.model_copy(update={"model": target_model})

        if pre_fallback:
            yield LLMStreamChunk(
                type="usage",
                resolved_model=target_model,
                actual_provider=actual_provider,
                fallback_used=True,
                fallback_from_model=fallback_from,
                routing_reason=fallback_reason,
            )

        has_yielded_token = False
        saw_error = False
        error_msg = ""

        try:
            async for chunk in provider.stream_chat(effective_req):
                if chunk.type == "error":
                    saw_error = True
                    error_msg = chunk.content
                    break
                if chunk.type in ["token", "reasoning"]:
                    has_yielded_token = True

                # Preserve truthful provider/model identity on every emitted chunk
                chunk.resolved_model = chunk.resolved_model or target_model
                chunk.actual_provider = chunk.actual_provider or actual_provider
                if pre_fallback:
                    chunk.fallback_used = True
                    chunk.fallback_from_model = fallback_from
                    chunk.resolved_model = target_model
                    chunk.actual_provider = actual_provider
                yield chunk

        except Exception as e:
            saw_error = True
            error_msg = str(e)

        # Runtime provider failure before tokens were emitted -> trigger fallback without masquerading
        if saw_error and not has_yielded_token:
            logger.warning(
                f"Provider '{actual_provider}' failed for '{request.model}' ({error_msg}). Triggering NEXORA fallback."
            )
            fallback_notice = (
                f"> *[Notice: Provider '{actual_provider}' for `{request.model}` unavailable "
                f"({error_msg}). Response transparently served by `nexora-flagship`.]*\n\n"
            )
            fallback_req = request.model_copy(update={"model": "nexora-flagship"})
            yield LLMStreamChunk(
                type="usage",
                resolved_model="nexora-flagship",
                actual_provider="nexora",
                fallback_used=True,
                fallback_from_model=request.model,
                routing_reason=f"Fallback to nexora-flagship due to provider error: {error_msg}",
            )
            yield LLMStreamChunk(
                type="token",
                content=fallback_notice,
                resolved_model="nexora-flagship",
                actual_provider="nexora",
                fallback_used=True,
                fallback_from_model=request.model,
            )
            async for chunk in self._fallback_provider.stream_chat(fallback_req):
                chunk.resolved_model = "nexora-flagship"
                chunk.actual_provider = "nexora"
                chunk.fallback_used = True
                chunk.fallback_from_model = request.model
                yield chunk

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Non-streaming generation with truthful provider & fallback metadata."""
        provider, target_model, actual_provider, pre_fallback, fallback_from, _ = (
            self.resolve_execution_target(request.model)
        )
        effective_req = request.model_copy(update={"model": target_model})

        try:
            resp = await provider.generate(effective_req)
            resp.model = target_model
            resp.actual_provider = actual_provider
            resp.fallback_used = pre_fallback
            resp.fallback_from_model = fallback_from
            return resp
        except Exception as e:
            logger.warning(f"Generate failed on provider '{actual_provider}' for '{request.model}': {e}. Using fallback.")
            fallback_req = request.model_copy(update={"model": "nexora-flagship"})
            resp = await self._fallback_provider.generate(fallback_req)
            resp.model = "nexora-flagship"
            resp.actual_provider = "nexora"
            resp.fallback_used = True
            resp.fallback_from_model = request.model
            return resp

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
                    error=str(report),
                )

        return results


gateway = UnifiedModelGateway()
llm_gateway = gateway
