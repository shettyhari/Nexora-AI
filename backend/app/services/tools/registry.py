import json
import time
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.tool_execution import ToolExecution
from app.services.llm.base import ToolDefinition
from app.services.tools.base import BaseTool, ToolExecutionContext, ToolExecutionResult, ToolPermissionLevel
from app.services.tools.builtin_tools import (
    DataVisualizerTool,
    DocumentCompareTool,
    DocumentExtractTool,
    OCRImageTool,
    PythonInterpreterTool,
    WebExtractTool,
    WebSearchTool,
)


class ToolRegistry:
    """Central registry and dispatch engine for all standardized AI tools in NEXORA AI."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        default_tools = [
            WebSearchTool(),
            WebExtractTool(),
            DocumentExtractTool(),
            DocumentCompareTool(),
            DataVisualizerTool(),
            OCRImageTool(),
            PythonInterpreterTool(),
        ]
        for t in default_tools:
            self.register_tool(t)

    def register_tool(self, tool: BaseTool) -> None:
        """Register a new tool instance."""
        self._tools[tool.tool_id] = tool

    def get_tool(self, tool_id: str) -> Optional[BaseTool]:
        """Retrieve tool by identifier."""
        return self._tools.get(tool_id)

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return metadata and schemas for all registered tools."""
        return [
            {
                "tool_id": t.tool_id,
                "name": t.name,
                "description": t.description,
                "permission_level": t.permission_level.value,
                "requires_approval": t.requires_approval,
                "timeout_seconds": t.timeout_seconds,
                "input_schema": t.input_schema,
                "output_schema": t.output_schema
            }
            for t in self._tools.values()
        ]

    def get_llm_tool_definitions(self, tool_ids: Optional[List[str]] = None) -> List[ToolDefinition]:
        """Convert tools to LLM ToolDefinitions for model function calling."""
        defs = []
        selected = [self._tools[tid] for tid in (tool_ids or self._tools.keys()) if tid in self._tools]
        for t in selected:
            defs.append(t.to_tool_definition())
        return defs

    async def execute_tool(
        self,
        tool_id: str,
        params: Dict[str, Any],
        context: ToolExecutionContext,
        db: Optional[AsyncSession] = None
    ) -> ToolExecutionResult:
        """Execute a tool with timeout safety, approval enforcement, and audit persistence."""
        tool = self.get_tool(tool_id)
        if not tool:
            return ToolExecutionResult(
                tool_id=tool_id,
                status="failed",
                error=f"Tool '{tool_id}' is not registered.",
                permission_level=ToolPermissionLevel.READ
            )

        start = time.time()

        # Check approval gate
        if tool.requires_approval and not context.is_approved:
            res = ToolExecutionResult(
                tool_id=tool.tool_id,
                status="pending_approval",
                output={"message": f"Action '{tool.name}' requires explicit approval before execution."},
                permission_level=tool.permission_level,
                requires_approval=True
            )
        else:
            try:
                res = await tool.execute(params, context)
            except Exception as e:
                res = ToolExecutionResult(
                    tool_id=tool.tool_id,
                    status="failed",
                    error=str(e),
                    execution_time_ms=(time.time() - start) * 1000,
                    permission_level=tool.permission_level
                )

        # Audit logging into database if db session provided
        if db:
            try:
                execution_record = ToolExecution(
                    id=str(uuid.uuid4()),
                    user_id=context.user_id,
                    tool_id=tool.tool_id,
                    permission_level=tool.permission_level.value,
                    status=res.status,
                    parameters_json=json.dumps(params)[:2000],
                    result_json=json.dumps(res.output if res.output else {})[:2000],
                    requires_approval=res.requires_approval,
                    approved_by=context.user_id if context.is_approved else None,
                    error=res.error,
                    execution_time_ms=res.execution_time_ms
                )
                db.add(execution_record)

                audit_entry = AuditLog(
                    id=str(uuid.uuid4()),
                    user_id=context.user_id,
                    action=f"tool_execution:{tool.tool_id}",
                    resource_type="tool",
                    resource_id=tool.tool_id,
                    details=json.dumps({
                        "status": res.status,
                        "permission_level": tool.permission_level.value,
                        "execution_time_ms": res.execution_time_ms
                    })
                )
                db.add(audit_entry)
                await db.commit()
                res.audit_id = execution_record.id
            except Exception:
                await db.rollback()

        return res


tool_registry = ToolRegistry()
