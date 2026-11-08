import json
import logging
from typing import AsyncGenerator, List, Optional
import httpx
from app.core.config import settings
from app.services.llm.base import BaseLLMProvider, LLMMessage, LLMStreamChunk, LLMUsage

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude LLM provider for NEXORA AI."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.base_url = "https://api.anthropic.com/v1"

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
                content="Anthropic API key is not configured. Please set ANTHROPIC_API_KEY in the backend environment."
            )
            return

        target_model = model
        if target_model in ["nexora-pro", "claude-3-5-sonnet"]:
            target_model = "claude-3-5-sonnet-20241022"

        formatted_messages = []
        for msg in messages:
            if msg.role != "system":
                formatted_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        payload = {
            "model": target_model,
            "messages": formatted_messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
            "stream": True
        }
        if system_prompt:
            payload["system"] = system_prompt

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        total_prompt_tokens = 0
        total_completion_tokens = 0

        try:
            url = f"{self.base_url}/messages"
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        try:
                            error_json = json.loads(error_body)
                            err_msg = error_json.get("error", {}).get("message", response.reason_phrase)
                        except Exception:
                            err_msg = error_body.decode("utf-8", errors="ignore")
                        yield LLMStreamChunk(type="error", content=f"Anthropic API Error ({response.status_code}): {err_msg}")
                        return

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        raw = line[6:].strip()
                        try:
                            event = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        event_type = event.get("type")
                        if event_type == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield LLMStreamChunk(type="token", content=delta.get("text", ""))
                            elif delta.get("type") == "thinking_delta":
                                yield LLMStreamChunk(type="reasoning", content=delta.get("thinking", ""))

                        elif event_type == "message_start":
                            msg = event.get("message", {})
                            usage = msg.get("usage", {})
                            total_prompt_tokens = usage.get("input_tokens", 0)

                        elif event_type == "message_delta":
                            usage = event.get("usage", {})
                            total_completion_tokens = usage.get("output_tokens", 0)

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
            yield LLMStreamChunk(type="error", content="Request to Anthropic timed out. Please try again.")
        except Exception as e:
            logger.exception("Anthropic stream error")
            yield LLMStreamChunk(type="error", content=f"Connection error with AI provider: {str(e)}")
