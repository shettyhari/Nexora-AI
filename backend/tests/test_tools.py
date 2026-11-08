import pytest
from app.services.tools.base import ToolExecutionContext, ToolPermissionLevel
from app.services.tools.registry import tool_registry


@pytest.mark.asyncio
async def test_tool_registry_default_tools():
    tools = tool_registry.list_tools()
    tool_ids = {t["tool_id"] for t in tools}
    assert "web_search" in tool_ids
    assert "web_extract" in tool_ids
    assert "document_extract" in tool_ids
    assert "document_compare" in tool_ids
    assert "data_visualizer" in tool_ids
    assert "ocr_image_reader" in tool_ids
    assert "python_interpreter" in tool_ids


@pytest.mark.asyncio
async def test_web_search_tool_execution():
    ctx = ToolExecutionContext(user_id="test_user_1")
    res = await tool_registry.execute_tool("web_search", {"query": "Next.js 14 architecture"}, ctx)
    assert res.status == "completed"
    assert res.permission_level == ToolPermissionLevel.READ
    assert len(res.output.get("results", [])) > 0


@pytest.mark.asyncio
async def test_data_visualizer_tool():
    ctx = ToolExecutionContext(user_id="test_user_1")
    params = {
        "chart_type": "bar",
        "title": "Quarterly Revenue",
        "labels": ["Q1", "Q2", "Q3", "Q4"],
        "datasets": [{"label": "Revenue ($M)", "data": [12.4, 15.2, 18.0, 22.5]}]
    }
    res = await tool_registry.execute_tool("data_visualizer", params, ctx)
    assert res.status == "completed"
    assert res.output["chart_type"] == "bar"
    assert len(res.output["labels"]) == 4


@pytest.mark.asyncio
async def test_python_interpreter_approval_gate():
    # Attempting to run without explicit approval should return pending_approval
    unapproved_ctx = ToolExecutionContext(user_id="test_user_1", is_approved=False)
    res = await tool_registry.execute_tool("python_interpreter", {"code": "print('hello')"}, unapproved_ctx)
    assert res.status == "pending_approval"
    assert res.requires_approval is True

    # With approval granted
    approved_ctx = ToolExecutionContext(user_id="test_user_1", is_approved=True)
    res_approved = await tool_registry.execute_tool("python_interpreter", {"code": "print(40 + 2)"}, approved_ctx)
    assert res_approved.status == "completed"
    assert "42" in res_approved.output["stdout"]
