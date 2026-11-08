import pytest
from app.services.router.model_router import model_router


@pytest.mark.asyncio
async def test_router_coding_accuracy():
    """Test router accurately identifies complex software engineering and routes to coding specialist."""
    prompt = "Implement a distributed lock manager in Rust using Tokio and async mutexes with lease timeouts."
    decision = model_router.route(requested_model_id="nexora-auto", prompt=prompt)

    assert decision.task_profile.requires_code is True
    assert decision.task_profile.complexity == "complex"
    assert decision.selected_model_id in ["claude-3-5-sonnet", "gpt-4o", "gemini-1.5-pro", "nexora-flagship"]
    assert "coding" in decision.reason.lower() or "architecture" in decision.reason.lower()


@pytest.mark.asyncio
async def test_router_deep_reasoning_accuracy():
    """Test router accurately classifies mathematical / formal deduction tasks."""
    prompt = "Derive and mathematically prove the Cauchy-Schwarz inequality for general inner product spaces step-by-step."
    decision = model_router.route(requested_model_id="nexora-auto", prompt=prompt)

    assert decision.task_profile.requires_reasoning is True
    assert decision.task_profile.intent == "deep_reasoning"
    assert decision.selected_model_id in ["gemini-1.5-pro", "gpt-4o", "nexora-flagship"]


@pytest.mark.asyncio
async def test_router_simple_fast_chat_accuracy():
    """Test router classifies simple queries to low-latency fast models."""
    prompt = "Hello"
    decision = model_router.route(requested_model_id="nexora-auto", prompt=prompt)

    assert decision.task_profile.complexity == "simple"
    assert decision.selected_model_id in ["gemini-1.5-flash", "gpt-4o-mini", "nexora-fast"]


@pytest.mark.asyncio
async def test_router_manual_override():
    """Test that explicit model selection by the user is strictly honored."""
    prompt = "Simple greeting"
    decision = model_router.route(requested_model_id="claude-3-5-sonnet", prompt=prompt)

    assert decision.is_override is True
    assert decision.selected_model_id == "claude-3-5-sonnet"
    assert "manual user override" in decision.reason.lower()


@pytest.mark.asyncio
async def test_router_api_evaluate(client, auth_headers):
    """Test the HTTP router evaluation endpoint."""
    resp = await client.post(
        "/api/v1/router/evaluate",
        headers=auth_headers,
        json={"prompt": "Write a Python script to compute Fibonacci numbers", "requested_model_id": "nexora-auto"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "selected_model_id" in data
    assert "provider" in data
    assert "reason" in data
    assert data["task_profile"]["requires_code"] is True
