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
    ToolCall,
)
from app.services.model_registry.registry import model_registry

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(BaseLLMProvider):
    """Adapter for OpenAI-compatible self-hosted endpoints (Ollama, vLLM, LM Studio, LocalAI)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self._explicit_base_url = base_url.rstrip("/") if base_url is not None else None
        self._explicit_api_key = api_key
        self.provider_name = "openai_compatible"

    @property
    def base_url(self) -> str:
        if self._explicit_base_url is not None:
            return self._explicit_base_url
        return (settings.OPENAI_COMPATIBLE_BASE_URL or "http://localhost:11434/v1").rstrip("/")

    @base_url.setter
    def base_url(self, value: Optional[str]) -> None:
        self._explicit_base_url = value.rstrip("/") if value is not None else None

    @property
    def api_key(self) -> str:
        if self._explicit_api_key is not None:
            return self._explicit_api_key
        return settings.OPENAI_COMPATIBLE_API_KEY or "ollama"

    @api_key.setter
    def api_key(self, value: Optional[str]) -> None:
        self._explicit_api_key = value

    def is_configured(self) -> bool:
        return bool(self.base_url and len(self.base_url) > 5)

    def _build_payload(
        self,
        messages: List[LLMMessage],
        model: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = True,
        tools: Optional[List[Any]] = None,
        response_format: Optional[Any] = None
    ) -> Dict[str, Any]:
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            msg_dict: Dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                msg_dict["tool_calls"] = [tc.model_dump() for tc in msg.tool_calls]
            formatted_messages.append(msg_dict)

        payload: Dict[str, Any] = {
            "model": model if model != "ollama-local" else "llama3.2",
            "messages": formatted_messages,
            "temperature": temperature,
            "stream": stream
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if tools:
            payload["tools"] = [t.model_dump() for t in tools]

        if response_format and response_format.type == "json_object":
            payload["response_format"] = {"type": "json_object"}

        return payload

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
            tools = req.tools
            response_format = req.response_format
        else:
            messages = messages_or_request
            model_id = model or "ollama-local"
            tools = None
            response_format = None

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = self._build_payload(
            messages=messages,
            model=model_id,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            tools=tools,
            response_format=response_format
        )

        total_prompt_tokens = 0
        total_completion_tokens = 0

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        yield LLMStreamChunk(type="error", content=f"Local Endpoint Error ({response.status_code}): {error_body.decode('utf-8', errors='ignore')}")
                        return

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break

                        try:
                            chunk_json = json.loads(data_str)
                            choices = chunk_json.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content_delta = delta.get("content", "")
                                if content_delta:
                                    total_completion_tokens += 1
                                    yield LLMStreamChunk(type="token", content=content_delta, resolved_model=model_id)

                            usage_data = chunk_json.get("usage")
                            if usage_data:
                                total_prompt_tokens = usage_data.get("prompt_tokens", total_prompt_tokens)
                                total_completion_tokens = usage_data.get("completion_tokens", total_completion_tokens)

                        except Exception:
                            continue

                    usage = LLMUsage(
                        prompt_tokens=total_prompt_tokens or 10,
                        completion_tokens=total_completion_tokens or 50,
                        total_tokens=(total_prompt_tokens or 10) + (total_completion_tokens or 50),
                        estimated_cost_usd=0.0
                    )
                    yield LLMStreamChunk(type="done", usage=usage, resolved_model=model_id)

        except Exception as e:
            yield LLMStreamChunk(type="error", content=f"OpenAI-Compatible Endpoint Connection Failure ({self.base_url}): {str(e)}")

    async def generate(self, request: LLMRequest) -> LLMResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = self._build_payload(
            messages=request.messages,
            model=request.model,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False,
            tools=request.tools,
            response_format=request.response_format
        )

        async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            choice = data["choices"][0]
            content = choice["message"].get("content", "")
            return LLMResponse(
                content=content,
                model=request.model,
                usage=LLMUsage(prompt_tokens=20, completion_tokens=100, total_tokens=120)
            )

    async def health_check(self) -> ProviderHealth:
        start_time = time.time()
        try:
            url = f"{self.base_url}/models"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(url, headers=headers)
                latency = round((time.time() - start_time) * 1000, 2)
                if resp.status_code == 200:
                    models = [m.get("id", "") for m in resp.json().get("data", [])][:6]
                    return ProviderHealth(
                        provider="openai_compatible",
                        status="online",
                        latency_ms=latency,
                        models=models
                    )
                return ProviderHealth(
                    provider="openai_compatible",
                    status="degraded",
                    latency_ms=latency,
                    error=f"HTTP {resp.status_code}"
                )
        except Exception as e:
            return ProviderHealth(
                provider="openai_compatible",
                status="offline",
                latency_ms=round((time.time() - start_time) * 1000, 2),
                error=str(e)
            )

