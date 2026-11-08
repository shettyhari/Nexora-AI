import pytest
from app.services.agents.base import AgentType
from app.services.agents.orchestrator import orchestrator_agent


@pytest.mark.asyncio
async def test_list_all_eight_agents():
    agents = orchestrator_agent.list_available_agents()
    agent_types = {a["type"] for a in agents}
    expected = {
        "orchestrator",
        "research",
        "coding",
        "data_analysis",
        "document",
        "browser",
        "vision",
        "personal_assistant"
    }
    assert expected.issubset(agent_types)


@pytest.mark.asyncio
async def test_orchestrator_planning_logic():
    # 1. Coding task plan
    coding_plan = await orchestrator_agent.plan_workflow("Write a Python script to sort a distributed dictionary")
    coding_agents = [step.agent_type for step in coding_plan]
    assert AgentType.CODING in coding_agents

    # 2. Research task plan
    research_plan = await orchestrator_agent.plan_workflow("Research latest breakthroughs in nuclear fusion energy")
    research_agents = [step.agent_type for step in research_plan]
    assert AgentType.RESEARCH in research_agents

    # 3. Vision task plan
    vision_plan = await orchestrator_agent.plan_workflow("Analyze the architecture diagram in this image")
    vision_agents = [step.agent_type for step in vision_plan]
    assert AgentType.VISION in vision_agents

    # 4. Data analysis plan
    data_plan = await orchestrator_agent.plan_workflow("Analyze this sales dataset and generate a chart")
    data_agents = [step.agent_type for step in data_plan]
    assert AgentType.DATA_ANALYSIS in data_agents


@pytest.mark.asyncio
async def test_orchestrator_workflow_execution():
    goal = "Research and summarize the best practices for FastAPI async architectures"
    result = await orchestrator_agent.execute_workflow(
        goal=goal,
        user_id="test_admin_user",
        conversation_id="conv_test_123"
    )

    assert result.status == "completed"
    assert len(result.plan) >= 1
    assert len(result.step_results) == len(result.plan)
    assert result.final_response != ""
    assert result.total_execution_time_ms >= 0

    # Ensure each step completed successfully
    for step_res in result.step_results:
        assert step_res.status == "completed"
        assert step_res.output != ""
