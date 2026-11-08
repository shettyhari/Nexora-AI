import json
import logging
from typing import AsyncGenerator, List, Optional
import httpx
from app.core.config import settings
from app.services.llm.base import BaseLLMProvider, LLMMessage, LLMStreamChunk, LLMUsage

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM provider for NEXORA AI."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

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
                content="Gemini API key is not configured. Please set GEMINI_API_KEY in the backend environment."
            )
            return

        # Normalize model name
        target_model = model
        if target_model in ["nexora-pro", "nexora-flash", "nexora-core"]:
            target_model = "gemini-1.5-flash"

        url = f"{self.base_url}/models/{target_model}:streamGenerateContent?alt=sse&key={self.api_key}"

        # Build contents
        contents = []
        for msg in messages:
            if msg.role == "system":
                # System prompt is passed in system_instruction
                continue
            role = "user" if msg.role == "user" else "model"
            parts = [{"text": msg.content}]
            contents.append({
                "role": role,
                "parts": parts
            })

        # Ensure at least one user message
        if not contents:
            contents = [{"role": "user", "parts": [{"text": "Hello"}]}]

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
            }
        }
        if max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens

        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        headers = {
            "Content-Type": "application/json"
        }

        total_prompt_tokens = 0
        total_completion_tokens = 0

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        try:
                            error_json = json.loads(error_body)
                            err_msg = error_json.get("error", {}).get("message", response.reason_phrase)
                        except Exception:
                            err_msg = error_body.decode("utf-8", errors="ignore")
                        yield LLMStreamChunk(type="error", content=f"Gemini API Error ({response.status_code}): {err_msg}")
                        return

                    buffer = ""
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            raw_data = line[6:].strip()
                            if raw_data == "[DONE]":
                                break
                            try:
                                data = json.loads(raw_data)
                            except json.JSONDecodeError:
                                continue

                            # Check for usage metadata
                            usage_meta = data.get("usageMetadata", {})
                            if usage_meta:
                                total_prompt_tokens = usage_meta.get("promptTokenCount", total_prompt_tokens)
                                total_completion_tokens = usage_meta.get("candidatesTokenCount", total_completion_tokens)

                            candidates = data.get("candidates", [])
                            if candidates:
                                candidate = candidates[0]
                                parts = candidate.get("content", {}).get("parts", [])
                                for part in parts:
                                    # Check for thought / reasoning
                                    if "thought" in part and part["thought"]:
                                        yield LLMStreamChunk(type="reasoning", content=part["text"])
                                    elif "text" in part and part["text"]:
                                        yield LLMStreamChunk(type="token", content=part["text"])

                                finish_reason = candidate.get("finishReason")
                                if finish_reason and finish_reason != "STOP":
                                    logger.info(f"Gemini finish reason: {finish_reason}")

            # Send usage & done
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
            yield LLMStreamChunk(type="error", content="Request to Gemini AI service timed out. Please try again.")
        except Exception as e:
            logger.exception("Gemini stream error")
            yield LLMStreamChunk(type="error", content=f"Connection error with AI provider: {str(e)}")
