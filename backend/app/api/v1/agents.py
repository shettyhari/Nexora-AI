from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.agent import AgentWorkflow
from app.models.user import User
from app.services.agents.orchestrator import orchestrator_agent

router = APIRouter(prefix="/agents", tags=["Multi-Agent Framework"])


class RunAgentWorkflowRequest(BaseModel):
    goal: str
    conversation_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


@router.get("/")
async def list_agents(current_user: User = Depends(get_current_user)):
    """List all 8 specialized agents in the NEXORA Multi-Agent Framework."""
    agents = orchestrator_agent.list_available_agents()
    return {
        "success": True,
        "count": len(agents),
        "agents": agents
    }


@router.post("/run")
async def run_agent_workflow(
    req: RunAgentWorkflowRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Execute an orchestrated multi-agent workflow with plan decomposition and step execution."""
    if not req.goal.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Goal cannot be empty.")

    try:
        result = await orchestrator_agent.execute_workflow(
            goal=req.goal,
            user_id=current_user.id,
            conversation_id=req.conversation_id,
            context=req.context,
            db=db
        )
        return {
            "success": True,
            "data": result.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve detailed state, plan, and execution timeline for an agent workflow."""
    q = (
        select(AgentWorkflow)
        .options(selectinload(AgentWorkflow.steps))
        .where(AgentWorkflow.id == workflow_id, AgentWorkflow.user_id == current_user.id)
    )
    res = await db.execute(q)
    wf = res.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found.")

    return {
        "id": wf.id,
        "title": wf.title,
        "goal": wf.goal,
        "status": wf.status,
        "final_result": wf.final_result,
        "created_at": wf.created_at.isoformat(),
        "steps": [
            {
                "id": s.id,
                "step_number": s.step_number,
                "agent_type": s.agent_type,
                "status": s.status,
                "description": s.description,
                "execution_time_ms": s.execution_time_ms,
                "output": s.output_json,
                "error": s.error
            }
            for s in wf.steps
        ]
    }
