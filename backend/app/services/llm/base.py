from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel


class LLMMessage(BaseModel):
    role: str  # 'system', 'user', 'assistant'
    content: str
    reasoning_content: Optional[str] = None
    images: Optional[List[str]] = None  # Base64 or image URLs


class LLMUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMStreamChunk(BaseModel):
    type: str = "token"  # "token", "reasoning", "usage", "done", "error"
    content: str = ""
    finish_reason: Optional[str] = None
    usage: Optional[LLMUsage] = None


class BaseLLMProvider(ABC):
    """Abstract base class for all AI LLM providers in NEXORA AI."""

    @abstractmethod
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
        """Stream response tokens and reasoning chunks asynchronously."""
        yield LLMStreamChunk(type="error", content="Not implemented")

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if required API keys / credentials are provided."""
        return False
