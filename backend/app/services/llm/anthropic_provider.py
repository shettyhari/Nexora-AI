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


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude LLM provider for NEXORA AI."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.base_url = "https://api.anthropic.com/v1"
        self.provider_name = "anthropic"

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def _normalize_model(self, model: str) -> str:
        if model in ["nexora-auto", "claude-3-5-sonnet", "nexora-pro"]:
            return "claude-3-5-sonnet-20241022"
        elif model in ["claude-3-5-haiku", "nexora-fast"]:
            return "claude-3-5-haiku-20241022"
        return model

    def _build_payload(
        self,
        messages: List[LLMMessage],
        model: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = True,
        tools: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        formatted_messages = []
        for msg in messages:
            if msg.role != "system":
                formatted_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        if not formatted_messages:
            formatted_messages = [{"role": "user", "content": "Hello"}]

        payload: Dict[str, Any] = {
            "model": model,
            "messages": formatted_messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
            "stream": stream
        }

        if system_prompt:
            payload["system"] = system_prompt

        if tools:
            anthropic_tools = []
            for t in tools:
                anthropic_tools.append({
                    "name": t.function.name,
                    "description": t.function.description or "",
                    "input_schema": t.function.parameters or {"type": "object", "properties": {}}
                })
            payload["tools"] = anthropic_tools

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
        else:
            messages = messages_or_request
            model_id = model or "claude-3-5-sonnet"
            tools = None

        if not self.is_configured():
            yield LLMStreamChunk(
                type="error",
                content="Anthropic API key is not configured. Please set ANTHROPIC_API_KEY in backend environment."
            )
            return

        target_model = self._normalize_model(model_id)
        url = f"{self.base_url}/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = self._build_payload(
            messages=messages,
            model=target_model,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            tools=tools
        )

        total_prompt_tokens = 0
        total_completion_tokens = 0
        max_retries = 3
        backoff = 1.0

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                    async with client.stream("POST", url, json=payload, headers=headers) as response:
                        if response.status_code == 429 or response.status_code >= 500:
                            if attempt < max_retries - 1:
                                await asyncio.sleep(backoff)
                                backoff *= 2.0
                                continue
                            error_body = await response.aread()
                            yield LLMStreamChunk(type="error", content=f"Anthropic API Error ({response.status_code}): {error_body.decode('utf-8', errors='ignore')}")
                            return

                        if response.status_code != 200:
                            error_body = await response.aread()
                            yield LLMStreamChunk(type="error", content=f"Anthropic API Error ({response.status_code}): {error_body.decode('utf-8', errors='ignore')}")
                            return

                        async for line in response.aiter_lines():
                            if not line or not line.startswith("data: "):
                                continue
                            data_str = line[6:].strip()
                            if not data_str:
                                continue

                            try:
                                chunk_json = json.loads(data_str)
                                event_type = chunk_json.get("type", "")

                                if event_type == "message_start":
                                    msg = chunk_json.get("message", {})
                                    usage = msg.get("usage", {})
                                    total_prompt_tokens = usage.get("input_tokens", total_prompt_tokens)

                                elif event_type == "content_block_delta":
                                    delta = chunk_json.get("delta", {})
                                    if delta.get("type") == "text_delta":
                                        yield LLMStreamChunk(type="token", content=delta.get("text", ""), resolved_model=target_model)

                                elif event_type == "message_delta":
                                    usage = chunk_json.get("usage", {})
                                    total_completion_tokens = usage.get("output_tokens", total_completion_tokens)

                            except Exception as e:
                                logger.debug(f"Anthropic chunk parse skip: {e}")

                        # Calculate final cost
                        cost = model_registry.calculate_cost(target_model, total_prompt_tokens, total_completion_tokens)
                        usage = LLMUsage(
                            prompt_tokens=total_prompt_tokens,
                            completion_tokens=total_completion_tokens,
                            total_tokens=total_prompt_tokens + total_completion_tokens,
                            estimated_cost_usd=cost
                        )
                        yield LLMStreamChunk(type="done", usage=usage, resolved_model=target_model)
                        return

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(backoff)
                    backoff *= 2.0
                    continue
                yield LLMStreamChunk(type="error", content=f"Anthropic Connection Timeout: {str(e)}")
                return
            except Exception as e:
                logger.error(f"Anthropic unexpected stream failure: {e}", exc_info=True)
                yield LLMStreamChunk(type="error", content=f"Anthropic Stream Exception: {str(e)}")
                return

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Non-streaming generation."""
        target_model = self._normalize_model(request.model)
        url = f"{self.base_url}/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = self._build_payload(
            messages=request.messages,
            model=target_model,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False,
            tools=request.tools
        )

        async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            content_text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content_text += block.get("text", "")

            usage_data = data.get("usage", {})
            p_tok = usage_data.get("input_tokens", 0)
            c_tok = usage_data.get("output_tokens", 0)
            cost = model_registry.calculate_cost(target_model, p_tok, c_tok)

            return LLMResponse(
                content=content_text,
                model=target_model,
                finish_reason=data.get("stop_reason", "stop"),
                usage=LLMUsage(
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    total_tokens=p_tok + c_tok,
                    estimated_cost_usd=cost
                )
            )

    async def health_check(self) -> ProviderHealth:
        """Ping Anthropic health."""
        if not self.is_configured():
            return ProviderHealth(
                provider="anthropic",
                status="offline",
                error="ANTHROPIC_API_KEY is not configured"
            )

        start_time = time.time()
        try:
            # Send minimal test request to verify API key validity
            url = f"{self.base_url}/messages"
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            payload = {
                "model": "claude-3-5-haiku-20241022",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}]
            }
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                latency = round((time.time() - start_time) * 1000, 2)
                if resp.status_code == 200:
                    return ProviderHealth(
                        provider="anthropic",
                        status="online",
                        latency_ms=latency,
                        models=["claude-3-5-sonnet", "claude-3-5-haiku", "claude-3-opus"]
                    )
                else:
                    return ProviderHealth(
                        provider="anthropic",
                        status="degraded",
                        latency_ms=latency,
                        error=f"HTTP {resp.status_code}"
                    )
        except Exception as e:
            return ProviderHealth(
                provider="anthropic",
                status="offline",
                latency_ms=round((time.time() - start_time) * 1000, 2),
                error=str(e)
            )
