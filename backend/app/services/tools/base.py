from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.services.llm.base import ToolDefinition, ToolFunction


class ToolPermissionLevel(str, Enum):
    READ = "read"          # Read-only external data or state (Search, scrape, get doc)
    ANALYZE = "analyze"    # Parsing, OCR, statistics, comparison (No state change)
    PREPARE = "prepare"    # Generating code, draft schemas, plan staging
    EXECUTE = "execute"    # State modifying, code running, irreversible actions


class ToolExecutionContext(BaseModel):
    user_id: str
    conversation_id: Optional[str] = None
    workflow_id: Optional[str] = None
    step_id: Optional[str] = None
    is_approved: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True


class ToolExecutionResult(BaseModel):
    tool_id: str
    status: str = "completed"  # completed, failed, pending_approval
    output: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    permission_level: ToolPermissionLevel
    requires_approval: bool = False
    audit_id: Optional[str] = None


class BaseTool(ABC):
    """Abstract base class for all NEXORA AI standardized tools."""

    tool_id: str
    name: str
    description: str
    permission_level: ToolPermissionLevel
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    timeout_seconds: float = 30.0
    requires_approval: bool = False

    def to_tool_definition(self) -> ToolDefinition:
        """Convert to standard LLM ToolDefinition for model function calling."""
        return ToolDefinition(
            type="function",
            function=ToolFunction(
                name=self.tool_id,
                description=f"[{self.permission_level.value.upper()}] {self.description}",
                parameters=self.input_schema
            )
        )

    @abstractmethod
    async def execute(
        self,
        params: Dict[str, Any],
        context: ToolExecutionContext
    ) -> ToolExecutionResult:
        """Execute the tool logic with structured params and security context."""
        raise NotImplementedError
