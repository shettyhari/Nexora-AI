import json
import time
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentStep as DBAgentStep, AgentWorkflow as DBAgentWorkflow
from app.services.agents.base import AgentStepPlan, AgentStepResult, AgentType, BaseAgent
from app.services.agents.specialized_agents import (
    BrowserAgent,
    CodingAgent,
    DataAnalysisAgent,
    DocumentAgent,
    PersonalAssistantAgent,
    ResearchAgent,
    VisionAgent,
)
from app.services.llm.base import LLMMessage, LLMRequest
from app.services.llm.gateway import llm_gateway


class MultiAgentWorkflowResult(BaseModel):
    workflow_id: str
    goal: str
    status: str = "completed"  # completed, failed, paused
    plan: List[AgentStepPlan] = Field(default_factory=list)
    step_results: List[AgentStepResult] = Field(default_factory=list)
    final_response: str = ""
    total_execution_time_ms: float = 0.0


class OrchestratorAgent(BaseAgent):
    agent_type = AgentType.ORCHESTRATOR
    name = "Orchestrator Agent"
    description = "Decomposes complex requests into multi-agent workflows, dispatches sub-agents, and synthesizes answers."
    system_prompt = (
        "You are the NEXORA Central Orchestration AI. You coordinate a team of specialized sub-agents: "
        "Research, Coding, Data Analysis, Document, Browser, Vision, and Personal Assistant. "
        "Formulate optimal execution plans and synthesize high-fidelity unified responses."
    )

    def __init__(self):
        self._agents: Dict[AgentType, BaseAgent] = {
            AgentType.RESEARCH: ResearchAgent(),
            AgentType.CODING: CodingAgent(),
            AgentType.DATA_ANALYSIS: DataAnalysisAgent(),
            AgentType.DOCUMENT: DocumentAgent(),
            AgentType.BROWSER: BrowserAgent(),
            AgentType.VISION: VisionAgent(),
            AgentType.PERSONAL_ASSISTANT: PersonalAssistantAgent(),
        }

    def get_agent(self, agent_type: AgentType) -> Optional[BaseAgent]:
        return self._agents.get(agent_type)

    def list_available_agents(self) -> List[Dict[str, Any]]:
        agents = [{"type": self.agent_type.value, "name": self.name, "description": self.description}]
        for a in self._agents.values():
            agents.append({
                "type": a.agent_type.value,
                "name": a.name,
                "description": a.description,
                "available_tools": a.available_tools
            })
        return agents

    async def plan_workflow(self, goal: str, context: Optional[Dict[str, Any]] = None) -> List[AgentStepPlan]:
        """Generate a decomposed step-by-step agent execution plan."""
        context = context or {}
        has_file = bool(context.get("file_path"))
        has_image = bool(context.get("is_image") or (context.get("file_path", "").endswith((".png", ".jpg", ".jpeg", ".webp"))))
        goal_lower = goal.lower()

        plan: List[AgentStepPlan] = []
        step_idx = 1

        # Check for image understanding
        if has_image or "image" in goal_lower or "photo" in goal_lower or "diagram" in goal_lower:
            plan.append(AgentStepPlan(
                step_number=step_idx,
                agent_type=AgentType.VISION,
                description=f"Inspect and extract visual details from input: {goal[:60]}",
                required_tools=["ocr_image_reader"]
            ))
            step_idx += 1

        # Check for document analysis
        elif has_file or "document" in goal_lower or "pdf" in goal_lower or "excel" in goal_lower:
            plan.append(AgentStepPlan(
                step_number=step_idx,
                agent_type=AgentType.DOCUMENT,
                description=f"Parse, extract, and index document content: {goal[:60]}",
                required_tools=["document_extract"]
            ))
            step_idx += 1

        # Check for research needs
        if "research" in goal_lower or "latest" in goal_lower or "search" in goal_lower or "who is" in goal_lower or "compare" in goal_lower:
            plan.append(AgentStepPlan(
                step_number=step_idx,
                agent_type=AgentType.RESEARCH,
                description=f"Conduct web research and gather verified citations for: {goal[:60]}",
                required_tools=["web_search", "web_extract"]
            ))
            step_idx += 1

        # Check for coding needs
        if "code" in goal_lower or "function" in goal_lower or "script" in goal_lower or "build" in goal_lower or "debug" in goal_lower or "algorithm" in goal_lower:
            plan.append(AgentStepPlan(
                step_number=step_idx,
                agent_type=AgentType.CODING,
                description=f"Implement, verify, and document clean code for: {goal[:60]}",
                required_tools=["python_interpreter"]
            ))
            step_idx += 1

        # Check for data analysis needs
        if "data" in goal_lower or "dataset" in goal_lower or "chart" in goal_lower or "metric" in goal_lower or "calculate" in goal_lower:
            plan.append(AgentStepPlan(
                step_number=step_idx,
                agent_type=AgentType.DATA_ANALYSIS,
                description=f"Compute data metrics and generate visual chart specification for: {goal[:60]}",
                required_tools=["data_visualizer"]
            ))
            step_idx += 1

        # Fallback to personal assistant if plan is empty
        if not plan:
            plan.append(AgentStepPlan(
                step_number=1,
                agent_type=AgentType.PERSONAL_ASSISTANT,
                description=f"Synthesize comprehensive advisory response for: {goal}",
                required_tools=[]
            ))

        return plan

    async def execute_workflow(
        self,
        goal: str,
        user_id: str,
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        db: Optional[AsyncSession] = None
    ) -> MultiAgentWorkflowResult:
        """Run an end-to-end multi-agent orchestration workflow with persistence and synthesis."""
        start_time = time.time()
        workflow_id = str(uuid.uuid4())
        context = context or {}
        context["user_id"] = user_id
        context["workflow_id"] = workflow_id

        # 1. Generate plan
        plan = await self.plan_workflow(goal, context)

        # Database record creation
        db_workflow = None
        if db:
            try:
                db_workflow = DBAgentWorkflow(
                    id=workflow_id,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    title=f"Workflow: {goal[:50]}",
                    goal=goal,
                    status="running",
                    plan_json=json.dumps([p.dict() for p in plan])
                )
                db.add(db_workflow)
                await db.commit()
            except Exception:
                await db.rollback()

        # 2. Sequential execution of planned steps
        step_results: List[AgentStepResult] = []
        cumulative_context = dict(context)

        for step in plan:
            agent = self.get_agent(step.agent_type)
            if not agent:
                continue

            step_res = await agent.process(
                task=step.description,
                context=cumulative_context,
                step_number=step.step_number
            )
            step_results.append(step_res)
            cumulative_context[f"step_{step.step_number}_output"] = step_res.output

            # Persist step in DB
            if db:
                try:
                    db_step = DBAgentStep(
                        id=str(uuid.uuid4()),
                        workflow_id=workflow_id,
                        step_number=step.step_number,
                        agent_type=step.agent_type.value,
                        status=step_res.status,
                        description=step.description,
                        input_json=json.dumps({"task": step.description}),
                        output_json=json.dumps({"output": step_res.output}),
                        tool_calls_json=json.dumps(step_res.tool_results),
                        error=step_res.error,
                        execution_time_ms=step_res.execution_time_ms
                    )
                    db.add(db_step)
                    await db.commit()
                except Exception:
                    await db.rollback()

        # 3. Final Orchestrator Synthesis
        synthesis_input = (
            f"Original Goal: {goal}\n\n"
            f"Multi-Agent Execution Log:\n" +
            "\n".join([
                f"Step {r.step_number} [{r.agent_type.value.upper()}]:\n{r.output}"
                for r in step_results
            ])
        )

        req = LLMRequest(
            model="nexora-flagship",
            system_prompt=(
                "You are NEXORA Central Orchestrator. Synthesize the findings of your specialized sub-agents "
                "into an elegant, executive-ready final answer. Highlight key solutions, provide code or citations "
                "when applicable, and present a coherent, structured conclusion."
            ),
            messages=[LLMMessage(role="user", content=synthesis_input)],
            temperature=0.3,
            stream=False
        )

        try:
            synth_res = await llm_gateway.generate(req)
            final_response = synth_res.content
        except Exception:
            final_response = "\n\n".join([f"### {r.agent_type.value.upper()} Findings\n{r.output}" for r in step_results])

        total_time = (time.time() - start_time) * 1000

        # Update workflow record in DB
        if db and db_workflow:
            try:
                db_workflow.status = "completed"
                db_workflow.final_result = final_response
                await db.commit()
            except Exception:
                await db.rollback()

        return MultiAgentWorkflowResult(
            workflow_id=workflow_id,
            goal=goal,
            status="completed",
            plan=plan,
            step_results=step_results,
            final_response=final_response,
            total_execution_time_ms=total_time
        )

    async def process(self, task: str, context: Dict[str, Any], step_number: int = 1) -> AgentStepResult:
        res = await self.execute_workflow(task, user_id=context.get("user_id", "system"))
        return AgentStepResult(
            step_number=step_number,
            agent_type=self.agent_type,
            status="completed",
            output=res.final_response,
            execution_time_ms=res.total_execution_time_ms
        )


orchestrator_agent = OrchestratorAgent()
