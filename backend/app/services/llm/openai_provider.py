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


class OpenAIProvider(BaseLLMProvider):
    """OpenAI Provider supporting GPT-4o, GPT-4o-mini, o1/o3-mini, structured output, and tools."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1"
    ):
        self._explicit_api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.provider_name = "openai"

    @property
    def api_key(self) -> Optional[str]:
        if self._explicit_api_key is not None:
            return self._explicit_api_key
        return settings.OPENAI_API_KEY

    @api_key.setter
    def api_key(self, value: Optional[str]) -> None:
        self._explicit_api_key = value

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def _normalize_model(self, model: str) -> str:
        if model in ["nexora-auto", "nexora-pro"]:
            return "gpt-4o"
        elif model in ["nexora-flash", "nexora-fast"]:
            return "gpt-4o-mini"
        return model

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
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            if msg.name:
                msg_dict["name"] = msg.name
            formatted_messages.append(msg_dict)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": formatted_messages,
            "stream": stream
        }

        # Handle models that don't support temperature (e.g. o1)
        if not model.startswith("o1"):
            payload["temperature"] = temperature

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if tools:
            payload["tools"] = [t.model_dump() for t in tools]

        if response_format:
            if response_format.type == "json_schema" and response_format.json_schema:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": response_format.json_schema
                }
            elif response_format.type == "json_object":
                payload["response_format"] = {"type": "json_object"}

        if stream:
            payload["stream_options"] = {"include_usage": True}

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
            model_id = model or "gpt-4o"
            tools = None
            response_format = None

        if not self.is_configured():
            yield LLMStreamChunk(
                type="error",
                content="OpenAI API key is not configured. Please set OPENAI_API_KEY in the backend environment."
            )
            return

        target_model = self._normalize_model(model_id)
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = self._build_payload(
            messages=messages,
            model=target_model,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            tools=tools,
            response_format=response_format
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
                            yield LLMStreamChunk(type="error", content=f"OpenAI API Error ({response.status_code}): {error_body.decode('utf-8', errors='ignore')}")
                            return

                        if response.status_code != 200:
                            error_body = await response.aread()
                            yield LLMStreamChunk(type="error", content=f"OpenAI API Error ({response.status_code}): {error_body.decode('utf-8', errors='ignore')}")
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
                                    reasoning_delta = delta.get("reasoning_content", "") or delta.get("reasoning", "")
                                    tool_calls_delta = delta.get("tool_calls", None)

                                    if reasoning_delta:
                                        yield LLMStreamChunk(type="reasoning", content=reasoning_delta, resolved_model=target_model)
                                    if content_delta:
                                        yield LLMStreamChunk(type="token", content=content_delta, resolved_model=target_model)
                                    if tool_calls_delta:
                                        yield LLMStreamChunk(
                                            type="tool_call",
                                            tool_calls=[ToolCall(
                                                id=tc.get("id", f"tc_{int(time.time()*1000)}"),
                                                type="function",
                                                function=tc.get("function", {})
                                            ) for tc in tool_calls_delta],
                                            resolved_model=target_model
                                        )

                                usage_data = chunk_json.get("usage")
                                if usage_data:
                                    total_prompt_tokens = usage_data.get("prompt_tokens", total_prompt_tokens)
                                    total_completion_tokens = usage_data.get("completion_tokens", total_completion_tokens)

                            except Exception as e:
                                logger.debug(f"OpenAI chunk parse skip: {e}")

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
                yield LLMStreamChunk(type="error", content=f"OpenAI Connection Error: {str(e)}")
                return
            except Exception as e:
                logger.error(f"OpenAI unexpected failure: {e}", exc_info=True)
                yield LLMStreamChunk(type="error", content=f"OpenAI Stream Exception: {str(e)}")
                return

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Non-streaming generation."""
        target_model = self._normalize_model(request.model)
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = self._build_payload(
            messages=request.messages,
            model=target_model,
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
            content_text = choice["message"].get("content", "")
            raw_tools = choice["message"].get("tool_calls", None)
            tool_calls = None
            if raw_tools:
                tool_calls = [ToolCall(
                    id=rt.get("id", ""),
                    type="function",
                    function=rt.get("function", {})
                ) for rt in raw_tools]

            usage_data = data.get("usage", {})
            p_tok = usage_data.get("prompt_tokens", 0)
            c_tok = usage_data.get("completion_tokens", 0)
            cost = model_registry.calculate_cost(target_model, p_tok, c_tok)

            return LLMResponse(
                content=content_text or "",
                tool_calls=tool_calls,
                model=target_model,
                finish_reason=choice.get("finish_reason", "stop"),
                usage=LLMUsage(
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    total_tokens=p_tok + c_tok,
                    estimated_cost_usd=cost
                )
            )

    async def health_check(self) -> ProviderHealth:
        """Ping OpenAI API to verify status and retrieve available models."""
        if not self.is_configured():
            return ProviderHealth(
                provider="openai",
                status="offline",
                error="OPENAI_API_KEY is not configured"
            )

        start_time = time.time()
        try:
            url = f"{self.base_url}/models"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers=headers)
                latency = round((time.time() - start_time) * 1000, 2)
                if resp.status_code == 200:
                    models = [m.get("id", "") for m in resp.json().get("data", [])][:8]
                    return ProviderHealth(
                        provider="openai",
                        status="online",
                        latency_ms=latency,
                        models=models
                    )
                else:
                    return ProviderHealth(
                        provider="openai",
                        status="degraded",
                        latency_ms=latency,
                        error=f"HTTP {resp.status_code}"
                    )
        except Exception as e:
            return ProviderHealth(
                provider="openai",
                status="offline",
                latency_ms=round((time.time() - start_time) * 1000, 2),
                error=str(e)
            )
