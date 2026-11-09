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


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM provider with streaming, tool calling, and health monitoring."""

    def __init__(self, api_key: Optional[str] = None):
        self._explicit_api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.provider_name = "google"

    @property
    def api_key(self) -> Optional[str]:
        if self._explicit_api_key is not None:
            return self._explicit_api_key
        return settings.GEMINI_API_KEY

    @api_key.setter
    def api_key(self, value: Optional[str]) -> None:
        self._explicit_api_key = value

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def _normalize_model(self, model: str) -> str:
        if model in ["nexora-auto", "nexora-pro", "nexora-flash", "nexora-core"]:
            return "gemini-1.5-flash"
        return model

    def _build_payload(
        self,
        messages: List[LLMMessage],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Any]] = None,
        response_format: Optional[Any] = None
    ) -> Dict[str, Any]:
        contents = []
        for msg in messages:
            if msg.role == "system":
                continue
            role = "user" if msg.role == "user" else "model"
            parts = [{"text": msg.content}]
            contents.append({"role": role, "parts": parts})

        if not contents:
            contents = [{"role": "user", "parts": [{"text": "Hello"}]}]

        gen_config: Dict[str, Any] = {"temperature": temperature}
        if max_tokens:
            gen_config["maxOutputTokens"] = max_tokens

        if response_format and response_format.type in ["json_object", "json_schema"]:
            gen_config["responseMimeType"] = "application/json"
            if response_format.json_schema:
                gen_config["responseSchema"] = response_format.json_schema

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": gen_config
        }

        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        if tools:
            function_declarations = []
            for t in tools:
                function_declarations.append({
                    "name": t.function.name,
                    "description": t.function.description or "",
                    "parameters": t.function.parameters or {}
                })
            payload["tools"] = [{"functionDeclarations": function_declarations}]

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
            model_id = model or "gemini-1.5-flash"
            tools = None
            response_format = None

        if not self.is_configured():
            yield LLMStreamChunk(
                type="error",
                content="Gemini API key is not configured. Please set GEMINI_API_KEY in backend environment."
            )
            return

        target_model = self._normalize_model(model_id)
        url = f"{self.base_url}/models/{target_model}:streamGenerateContent?alt=sse&key={self.api_key}"
        payload = self._build_payload(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            response_format=response_format
        )
        headers = {"Content-Type": "application/json"}

        total_prompt_tokens = 0
        total_completion_tokens = 0

        # Retry logic with exponential backoff for transient failures
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
                            yield LLMStreamChunk(type="error", content=f"Gemini API Error ({response.status_code}): {error_body.decode('utf-8', errors='ignore')}")
                            return

                        if response.status_code != 200:
                            error_body = await response.aread()
                            yield LLMStreamChunk(type="error", content=f"Gemini API Error ({response.status_code}): {error_body.decode('utf-8', errors='ignore')}")
                            return

                        async for line in response.aiter_lines():
                            if not line or not line.startswith("data: "):
                                continue
                            data_str = line[6:].strip()
                            if not data_str:
                                continue

                            try:
                                chunk_json = json.loads(data_str)
                                candidates = chunk_json.get("candidates", [])
                                if candidates:
                                    parts = candidates[0].get("content", {}).get("parts", [])
                                    for part in parts:
                                        if "text" in part and part["text"]:
                                            yield LLMStreamChunk(type="token", content=part["text"], resolved_model=target_model)
                                        if "functionCall" in part:
                                            fc = part["functionCall"]
                                            yield LLMStreamChunk(
                                                type="tool_call",
                                                tool_calls=[ToolCall(
                                                    id=f"call_{int(time.time()*1000)}",
                                                    type="function",
                                                    function={"name": fc.get("name", ""), "arguments": json.dumps(fc.get("args", {}))}
                                                )],
                                                resolved_model=target_model
                                            )

                                usage_meta = chunk_json.get("usageMetadata", {})
                                if usage_meta:
                                    total_prompt_tokens = usage_meta.get("promptTokenCount", total_prompt_tokens)
                                    total_completion_tokens = usage_meta.get("candidatesTokenCount", total_completion_tokens)

                            except Exception as e:
                                logger.debug(f"Gemini chunk parse skip: {e}")

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
                yield LLMStreamChunk(type="error", content=f"Gemini Connection Timeout: {str(e)}")
                return
            except Exception as e:
                logger.error(f"Gemini unexpected stream failure: {e}", exc_info=True)
                yield LLMStreamChunk(type="error", content=f"Gemini Stream Exception: {str(e)}")
                return

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Non-streaming generation."""
        target_model = self._normalize_model(request.model)
        url = f"{self.base_url}/models/{target_model}:generateContent?key={self.api_key}"
        payload = self._build_payload(
            messages=request.messages,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            tools=request.tools,
            response_format=request.response_format
        )

        async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

            candidates = data.get("candidates", [])
            content_text = ""
            tool_calls = []
            if candidates:
                for part in candidates[0].get("content", {}).get("parts", []):
                    if "text" in part:
                        content_text += part["text"]
                    if "functionCall" in part:
                        fc = part["functionCall"]
                        tool_calls.append(ToolCall(
                            id=f"call_{int(time.time()*1000)}",
                            type="function",
                            function={"name": fc.get("name", ""), "arguments": json.dumps(fc.get("args", {}))}
                        ))

            usage_meta = data.get("usageMetadata", {})
            p_tok = usage_meta.get("promptTokenCount", 0)
            c_tok = usage_meta.get("candidatesTokenCount", 0)
            cost = model_registry.calculate_cost(target_model, p_tok, c_tok)

            return LLMResponse(
                content=content_text,
                tool_calls=tool_calls if tool_calls else None,
                model=target_model,
                finish_reason="stop",
                usage=LLMUsage(
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    total_tokens=p_tok + c_tok,
                    estimated_cost_usd=cost
                )
            )

    async def health_check(self) -> ProviderHealth:
        """Verify API credentials and connectivity."""
        if not self.is_configured():
            return ProviderHealth(
                provider="google",
                status="offline",
                error="GEMINI_API_KEY is not configured"
            )

        start_time = time.time()
        try:
            url = f"{self.base_url}/models?key={self.api_key}"
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url)
                latency = round((time.time() - start_time) * 1000, 2)
                if resp.status_code == 200:
                    models_data = resp.json().get("models", [])
                    model_names = [m.get("name", "").replace("models/", "") for m in models_data][:8]
                    return ProviderHealth(
                        provider="google",
                        status="online",
                        latency_ms=latency,
                        models=model_names
                    )
                else:
                    return ProviderHealth(
                        provider="google",
                        status="degraded",
                        latency_ms=latency,
                        error=f"HTTP {resp.status_code}"
                    )
        except Exception as e:
            return ProviderHealth(
                provider="google",
                status="offline",
                latency_ms=round((time.time() - start_time) * 1000, 2),
                error=str(e)
            )
