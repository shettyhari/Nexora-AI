import json
import logging
from typing import AsyncGenerator, List, Optional
import httpx
from app.core.config import settings
from app.services.llm.base import BaseLLMProvider, LLMMessage, LLMStreamChunk, LLMUsage

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI and OpenAI-compatible (Groq, OpenRouter, DeepSeek) provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1"
    ):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.base_url = base_url.rstrip("/")

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    async def stream_chat(
        self,
        messages: List[LLMMessage],
        model: str,
        system_prompt: Optional[str] = None,
        reasoning_mode: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout_seconds: float = 60.0
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        if not self.is_configured():
            yield LLMStreamChunk(
                type="error",
                content="OpenAI/Compatible API key is not configured. Please set OPENAI_API_KEY in the backend environment."
            )
            return

        target_model = model
        if target_model in ["nexora-pro", "nexora-flash"]:
            target_model = "gpt-4o-mini"

        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            formatted_messages.append({
                "role": msg.role,
                "content": msg.content
            })

        payload = {
            "model": target_model,
            "messages": formatted_messages,
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True}
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        total_prompt_tokens = 0
        total_completion_tokens = 0

        try:
            url = f"{self.base_url}/chat/completions"
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        try:
                            error_json = json.loads(error_body)
                            err_msg = error_json.get("error", {}).get("message", response.reason_phrase)
                        except Exception:
                            err_msg = error_body.decode("utf-8", errors="ignore")
                        yield LLMStreamChunk(type="error", content=f"AI Provider Error ({response.status_code}): {err_msg}")
                        return

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        raw = line[6:].strip()
                        if raw == "[DONE]":
                            break
                        try:
                            chunk = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        # Check usage
                        if "usage" in chunk and chunk["usage"]:
                            u = chunk["usage"]
                            total_prompt_tokens = u.get("prompt_tokens", total_prompt_tokens)
                            total_completion_tokens = u.get("completion_tokens", total_completion_tokens)

                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            # Check reasoning content (DeepSeek / o1 / OpenAI style)
                            if "reasoning_content" in delta and delta["reasoning_content"]:
                                yield LLMStreamChunk(type="reasoning", content=delta["reasoning_content"])
                            if "content" in delta and delta["content"]:
                                yield LLMStreamChunk(type="token", content=delta["content"])

            yield LLMStreamChunk(
                type="usage",
                usage=LLMUsage(
                    prompt_tokens=total_prompt_tokens,
                    completion_tokens=total_completion_tokens,
                    total_tokens=total_prompt_tokens + total_completion_tokens
                )
            )
            yield LLMStreamChunk(type="done", finish_reason="stop")

        except httpx.TimeoutException:
            yield LLMStreamChunk(type="error", content="Request to AI service timed out. Please try again.")
        except Exception as e:
            logger.exception("OpenAI stream error")
            yield LLMStreamChunk(type="error", content=f"Connection error with AI provider: {str(e)}")
