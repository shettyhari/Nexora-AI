import pytest
from app.services.llm.base import LLMMessage
from app.services.llm.factory import LLMFactory
from app.services.llm.gemini import GeminiProvider


@pytest.mark.asyncio
async def test_llm_factory_fallback():
    provider = LLMFactory.get_provider("nexora-pro")
    assert provider is not None

    messages = [LLMMessage(role="user", content="Test prompt")]
    chunks = []
    async for chunk in provider.stream_chat(messages, model="nexora-pro"):
        chunks.append(chunk)

    assert len(chunks) > 0
    token_chunks = [c for c in chunks if c.type == "token"]
    assert len(token_chunks) > 0
    assert any(c.type == "done" for c in chunks)


@pytest.mark.asyncio
async def test_gemini_unconfigured_error():
    unconfigured_gemini = GeminiProvider(api_key="")
    assert unconfigured_gemini.is_configured() is False

    messages = [LLMMessage(role="user", content="Hello")]
    chunks = []
    async for chunk in unconfigured_gemini.stream_chat(messages, model="gemini-1.5-flash"):
        chunks.append(chunk)

    assert any(c.type == "error" for c in chunks)

