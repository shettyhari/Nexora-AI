from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentType(str, Enum):
    ORCHESTRATOR = "orchestrator"
    RESEARCH = "research"
    CODING = "coding"
    DATA_ANALYSIS = "data_analysis"
    DOCUMENT = "document"
    BROWSER = "browser"
    VISION = "vision"
    PERSONAL_ASSISTANT = "personal_assistant"


class AgentStepPlan(BaseModel):
    step_number: int
    agent_type: AgentType
    description: str
    required_tools: List[str] = Field(default_factory=list)


class AgentStepResult(BaseModel):
    step_number: int
    agent_type: AgentType
    status: str = "completed"  # completed, failed, waiting_approval
    output: str = ""
    structured_data: Optional[Dict[str, Any]] = None
    tool_results: List[Dict[str, Any]] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    error: Optional[str] = None


class BaseAgent(ABC):
    """Abstract base class for all specialized NEXORA AI sub-agents."""

    agent_type: AgentType
    name: str
    description: str
    system_prompt: str
    available_tools: List[str] = []

    @abstractmethod
    async def process(
        self,
        task: str,
        context: Dict[str, Any],
        step_number: int = 1
    ) -> AgentStepResult:
        """Execute agent-specific reasoning and tool utilization for the assigned task."""
        raise NotImplementedError
