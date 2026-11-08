from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.tools.base import ToolExecutionContext
from app.services.tools.registry import tool_registry
from app.services.tools.sandbox import isolated_sandbox

router = APIRouter(prefix="/tools", tags=["Tool Execution Engine"])


class ToolExecuteRequest(BaseModel):
    tool_id: str
    params: Dict[str, Any]
    conversation_id: Optional[str] = None
    is_approved: bool = False


class PythonSandboxRequest(BaseModel):
    code: str
    timeout_seconds: float = 10.0


@router.get("/")
async def list_registered_tools(current_user: User = Depends(get_current_user)):
    """List all registered tools, their schemas, and required permission levels."""
    tools = tool_registry.list_tools()
    return {
        "success": True,
        "count": len(tools),
        "tools": tools
    }


@router.post("/execute")
async def execute_tool(
    req: ToolExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Execute a tool with permission level enforcement, approval gating, and audit logging."""
    tool = tool_registry.get_tool(req.tool_id)
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tool '{req.tool_id}' not found.")

    ctx = ToolExecutionContext(
        user_id=current_user.id,
        conversation_id=req.conversation_id,
        is_approved=req.is_approved
    )

    result = await tool_registry.execute_tool(req.tool_id, req.params, ctx, db=db)
    return {
        "success": result.status == "completed",
        "result": result.dict()
    }


@router.post("/sandbox/python")
async def run_in_sandbox(
    req: PythonSandboxRequest,
    current_user: User = Depends(get_current_user)
):
    """Execute Python code in an isolated subprocess with strict AST validation."""
    if not req.code.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Code cannot be empty.")

    res = isolated_sandbox.run_code(req.code, timeout_seconds=req.timeout_seconds)
    return {
        "success": res.success,
        "result": res.dict()
    }
