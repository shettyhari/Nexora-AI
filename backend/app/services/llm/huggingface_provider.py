import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
import httpx
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
from app.services.model_registry.registry import model_registry

logger = logging.getLogger(__name__)


class HuggingFaceProvider(BaseLLMProvider):
    """Hugging Face Inference API / Dedicated Endpoints provider."""

    def __init__(self, api_key: Optional[str] = None, endpoint_url: Optional[str] = None):
        self.api_key = api_key or settings.HUGGINGFACE_API_KEY
        self.endpoint_url = endpoint_url or settings.HUGGINGFACE_ENDPOINT_URL
        self.provider_name = "huggingface"

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def _resolve_model_repo(self, model: str) -> str:
        mapping = {
            "hf-llama-3-70b": "meta-llama/Meta-Llama-3.1-70B-Instruct",
            "hf-deepseek-r1": "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
            "hf-qwen-72b": "Qwen/Qwen2.5-72B-Instruct",
        }
        return mapping.get(model, model)

    async def stream_chat(
        self,
        messages_or_request: Union[List[LLMMessage], LLMRequest],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        reasoning_mode: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout_seconds: float = 60.0
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        if isinstance(messages_or_request, LLMRequest):
            req = messages_or_request
            messages = req.messages
            model_id = req.model
            system_prompt = req.system_prompt
            temperature = req.temperature
            max_tokens = req.max_tokens
            timeout_seconds = req.timeout_seconds
        else:
            messages = messages_or_request
            model_id = model or "hf-llama-3-70b"

        if not self.is_configured():
            yield LLMStreamChunk(
                type="error",
                content="Hugging Face API key is not configured. Please set HUGGINGFACE_API_KEY in the backend environment."
            )
            return

        model_repo = self._resolve_model_repo(model_id)
        # Use Hugging Face OpenAI-compatible chat router or dedicated endpoint
        url = self.endpoint_url or f"https://api-inference.huggingface.co/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            formatted_messages.append({"role": msg.role, "content": msg.content})

        payload = {
            "model": model_repo,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 2048,
            "stream": True
        }

        prompt_chars = sum(len(m.content) for m in messages)
        est_prompt_tokens = max(1, prompt_chars // 4)
        completion_chars = 0

        max_retries = 2
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                    async with client.stream("POST", url, json=payload, headers=headers) as response:
                        if response.status_code != 200:
                            error_body = await response.aread()
                            yield LLMStreamChunk(type="error", content=f"Hugging Face Error ({response.status_code}): {error_body.decode('utf-8', errors='ignore')}")
                            return

                        async for line in response.aiter_lines():
                            if not line or not line.startswith("data: "):
                                continue
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                choices = chunk.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        completion_chars += len(content)
                                        yield LLMStreamChunk(type="token", content=content, resolved_model=model_id)
                            except Exception:
                                continue

                        est_completion_tokens = max(1, completion_chars // 4)
                        cost = model_registry.calculate_cost(model_id, est_prompt_tokens, est_completion_tokens)
                        usage = LLMUsage(
                            prompt_tokens=est_prompt_tokens,
                            completion_tokens=est_completion_tokens,
                            total_tokens=est_prompt_tokens + est_completion_tokens,
                            estimated_cost_usd=cost
                        )
                        yield LLMStreamChunk(type="done", usage=usage, resolved_model=model_id)
                        return
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.0)
                    continue
                yield LLMStreamChunk(type="error", content=f"Hugging Face Stream Error: {str(e)}")
                return

    async def generate(self, request: LLMRequest) -> LLMResponse:
        model_repo = self._resolve_model_repo(request.model)
        url = self.endpoint_url or f"https://api-inference.huggingface.co/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        formatted_messages = []
        if request.system_prompt:
            formatted_messages.append({"role": "system", "content": request.system_prompt})
        for msg in request.messages:
            formatted_messages.append({"role": msg.role, "content": msg.content})

        payload = {
            "model": model_repo,
            "messages": formatted_messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens or 2048,
            "stream": False
        }

        async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
            usage_data = data.get("usage", {})
            p_tok = usage_data.get("prompt_tokens", 0)
            c_tok = usage_data.get("completion_tokens", 0)
            cost = model_registry.calculate_cost(request.model, p_tok, c_tok)

            return LLMResponse(
                content=content,
                model=request.model,
                usage=LLMUsage(
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    total_tokens=p_tok + c_tok,
                    estimated_cost_usd=cost
                )
            )

    async def health_check(self) -> ProviderHealth:
        if not self.is_configured():
            return ProviderHealth(
                provider="huggingface",
                status="offline",
                error="HUGGINGFACE_API_KEY is not configured"
            )

        start_time = time.time()
        try:
            url = f"https://huggingface.co/api/whoami-v2"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers=headers)
                latency = round((time.time() - start_time) * 1000, 2)
                if resp.status_code == 200:
                    return ProviderHealth(
                        provider="huggingface",
                        status="online",
                        latency_ms=latency,
                        models=["hf-llama-3-70b", "hf-deepseek-r1", "hf-qwen-72b"]
                    )
                return ProviderHealth(
                    provider="huggingface",
                    status="degraded",
                    latency_ms=latency,
                    error=f"HTTP {resp.status_code}"
                )
        except Exception as e:
            return ProviderHealth(
                provider="huggingface",
                status="offline",
                latency_ms=round((time.time() - start_time) * 1000, 2),
                error=str(e)
            )
