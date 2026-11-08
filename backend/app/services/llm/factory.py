import asyncio
import logging
import sys
from typing import AsyncGenerator, List, Optional
from app.core.config import settings
from app.services.llm.base import BaseLLMProvider, LLMMessage, LLMStreamChunk, LLMUsage
from app.services.llm.gemini import GeminiProvider
from app.services.llm.openai_provider import OpenAIProvider
from app.services.llm.anthropic_provider import AnthropicProvider

logger = logging.getLogger(__name__)


class LocalFallbackProvider(BaseLLMProvider):
    """
    Fallback provider used when no external API key is configured.
    Delivers a streaming response demonstrating full NEXORA Markdown, code,
    tables, math, and reasoning capabilities, along with instructions to set a live key.
    """

    def is_configured(self) -> bool:
        return True

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
        user_msg = messages[-1].content if messages else "Hello"

        if reasoning_mode:
            thoughts = [
                "Analyzing user query: \"" + user_msg[:40] + "\"... ",
                "Checking system state and LLM provider configurations. ",
                "Synthesizing response with formatting elements..."
            ]
            for thought in thoughts:
                yield LLMStreamChunk(type="reasoning", content=thought)
                await asyncio.sleep(0.001)

        greeting = (
            f"### Welcome to **NEXORA AI**\n\n"
            f"You asked: *\"{user_msg}\"*\n\n"
            f"You are currently connected using **NEXORA Core Engine** (`{model}`).\n\n"
            f"> [!NOTE]\n"
            f"> To connect your live cloud LLM (such as Google Gemini, OpenAI GPT-4o, or Anthropic Claude), "
            f"simply add your key in the backend `.env` file:\n"
            f"> ```bash\n"
            f"> GEMINI_API_KEY=your_gemini_api_key_here\n"
            f"> OPENAI_API_KEY=your_openai_api_key_here\n"
            f"> ```\n\n"
            f"#### Code Execution & Markdown Preview\n"
            f"Here is a sample Python snippet rendered with full syntax highlighting:\n\n"
            f"```python\n"
            f"def nexora_accelerate(query: str) -> dict:\n"
            f"    \"\"\"Process prompt with streaming neural context.\"\"\"\n"
            f"    return {{\n"
            f"        'status': 'active',\n"
            f"        'model': '{model}',\n"
            f"        'query_length': len(query),\n"
            f"        'streaming': True\n"
            f"    }}\n"
            f"```\n\n"
            f"#### Feature Matrix\n"
            f"| Capability | Status | Latency |\n"
            f"| :--- | :--- | :--- |\n"
            f"| Streaming Tokens | Ready | < 50ms |\n"
            f"| Syntax Highlighting | Active | Instant |\n"
            f"| LaTeX Equations | Supported | Native |\n"
            f"| Deep Reasoning | Enabled | Variable |\n\n"
            f"#### Mathematical Representation\n"
            f"Self-attention mechanism formula:\n\n"
            f"$$\\text{{Attention}}(Q, K, V) = \\text{{softmax}}\\left(\\frac{{QK^T}}{{\\sqrt{{d_k}}}}\\right)V$$\n\n"
            f"Let me know what you would like to build or analyze next!"
        )

        words = greeting.split(" ")
        for i, word in enumerate(words):
            yield LLMStreamChunk(type="token", content=word + (" " if i < len(words) - 1 else ""))
            await asyncio.sleep(0.001)

        yield LLMStreamChunk(
            type="usage",
            usage=LLMUsage(
                prompt_tokens=len(user_msg.split()),
                completion_tokens=len(words),
                total_tokens=len(user_msg.split()) + len(words)
            )
        )
        yield LLMStreamChunk(type="done", finish_reason="stop")


class LLMFactory:
    """Factory for selecting and instantiating LLM providers."""

    @staticmethod
    def get_provider(model: Optional[str] = None) -> BaseLLMProvider:
        model_str = (model or settings.DEFAULT_MODEL_ID).lower()

        # Check explicit model names or provider mappings
        if "gemini" in model_str:
            gemini = GeminiProvider()
            if gemini.is_configured():
                return gemini

        if "gpt" in model_str or "o1" in model_str or "openai" in model_str or "groq" in model_str:
            openai_p = OpenAIProvider()
            if openai_p.is_configured():
                return openai_p

        if "claude" in model_str or "anthropic" in model_str:
            claude = AnthropicProvider()
            if claude.is_configured():
                return claude

        # For nexora-pro / nexora-flash / default model:
        # Check available keys in priority order: Gemini -> OpenAI -> Anthropic
        if settings.GEMINI_API_KEY:
            return GeminiProvider()
        if settings.OPENAI_API_KEY:
            return OpenAIProvider()
        if settings.ANTHROPIC_API_KEY:
            return AnthropicProvider()

        # Fallback provider if no keys are set
        return LocalFallbackProvider()
