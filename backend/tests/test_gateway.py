import pytest
from app.services.llm.base import LLMMessage, LLMRequest, ResponseFormat
from app.services.llm.gateway import gateway
from app.services.model_registry.registry import model_registry


@pytest.mark.asyncio
async def test_model_registry_models():
    """Test model registry catalogues all providers, context limits, and pricing."""
    models = model_registry.list_models()
    assert len(models) >= 8

    model_ids = [m.id for m in models]
    assert "nexora-auto" in model_ids
    assert "nexora-flagship" in model_ids
    assert "gemini-1.5-pro" in model_ids
    assert "gpt-4o" in model_ids
    assert "claude-3-5-sonnet" in model_ids

    # Test pricing calculation
    cost = model_registry.calculate_cost("gpt-4o", prompt_tokens=1000, completion_tokens=500)
    assert cost > 0.0


@pytest.mark.asyncio
async def test_gateway_health_checks():
    """Test concurrent health checks across all integrated providers."""
    health_reports = await gateway.check_all_health()
    assert "nexora" in health_reports
    assert health_reports["nexora"].status == "online"
    assert "google" in health_reports
    assert "openai" in health_reports
    assert "anthropic" in health_reports


@pytest.mark.asyncio
async def test_gateway_streaming_and_fallback():
    """Test that streaming through gateway succeeds and falls back gracefully when external keys are omitted."""
    req = LLMRequest(
        messages=[LLMMessage(role="user", content="Explain binary heaps in Python.")],
        model="nexora-flagship",
        reasoning_mode=True
    )

    tokens = []
    has_reasoning = False
    resolved_model = ""

    async for chunk in gateway.stream(req):
        if chunk.type == "token":
            tokens.append(chunk.content)
        elif chunk.type == "reasoning":
            has_reasoning = True
        if chunk.resolved_model:
            resolved_model = chunk.resolved_model

    full_text = "".join(tokens)
    assert len(full_text) > 20
    assert has_reasoning is True
    assert resolved_model != ""


@pytest.mark.asyncio
async def test_gateway_structured_output():
    """Test structured JSON output generation via gateway."""
    req = LLMRequest(
        messages=[LLMMessage(role="user", content="Evaluate system load parameters.")],
        model="nexora-flagship",
        response_format=ResponseFormat(type="json_object")
    )

    resp = await gateway.generate(req)
    assert resp.content != ""
    assert "status" in resp.content or "result" in resp.content
    assert resp.usage.total_tokens > 0
