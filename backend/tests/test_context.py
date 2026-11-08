import pytest
from app.services.context.context_manager import context_manager
from app.services.llm.base import LLMMessage


@pytest.mark.asyncio
async def test_context_token_counting():
    """Test token counting accuracy and message framing overhead."""
    text = "The quick brown fox jumps over the lazy dog."
    count = context_manager.count_tokens(text, model_id="gpt-4o")
    assert count >= 8 and count <= 12

    messages = [
        LLMMessage(role="user", content="Hello"),
        LLMMessage(role="assistant", content="Hi there! How can I assist you today?")
    ]
    total_tokens = context_manager.count_messages_tokens(messages, model_id="gpt-4o")
    assert total_tokens > count


@pytest.mark.asyncio
async def test_context_model_budgeting():
    """Test budget calculation per model context window."""
    gemini_budget = context_manager.get_model_budget("gemini-1.5-pro")
    assert gemini_budget["context_window"] == 2000000
    assert gemini_budget["available_input"] > 1000000

    gpt_budget = context_manager.get_model_budget("gpt-4o")
    assert gpt_budget["context_window"] == 128000
    assert gpt_budget["available_input"] > 100000


@pytest.mark.asyncio
async def test_context_compression_and_summarization():
    """Test older message history compression when context limit is exceeded."""
    # Generate 10 long turns
    long_history = []
    for i in range(10):
        long_history.append(LLMMessage(role="user", content=f"User discussion point {i}: " + ("x" * 200)))
        long_history.append(LLMMessage(role="assistant", content=f"Assistant technical reply {i}: " + ("y" * 300)))

    # Set tight token limit
    compressed = context_manager.compress_conversation_history(
        messages=long_history,
        max_tokens=250,
        model_id="gpt-4o",
        keep_recent_turns=2
    )

    # Must contain executive summary block for older messages
    assert len(compressed) < len(long_history)
    assert any("SUMMARY OF EARLIER MESSAGES" in m.content for m in compressed)
    # The last 2 turns must be preserved intact
    assert compressed[-1].content == long_history[-1].content
