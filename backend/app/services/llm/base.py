from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class ToolFunction(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class ToolDefinition(BaseModel):
    type: str = "function"
    function: ToolFunction


class ToolCall(BaseModel):
    id: str
    type: str = "function"
    function: Dict[str, str]  # {"name": "...", "arguments": "{...}"}


class ResponseFormat(BaseModel):
    type: str = "text"  # "text", "json_object", "json_schema"
    json_schema: Optional[Dict[str, Any]] = None


class LLMMessage(BaseModel):
    role: str  # 'system', 'user', 'assistant', 'tool'
    content: str
    reasoning_content: Optional[str] = None
    images: Optional[List[str]] = None  # Base64 or image URLs
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class LLMUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class LLMRequest(BaseModel):
    messages: List[LLMMessage]
    model: str = "nexora-flagship"
    system_prompt: Optional[str] = None
    reasoning_mode: bool = False
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    tools: Optional[List[ToolDefinition]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    response_format: Optional[ResponseFormat] = None
    stream: bool = True
    timeout_seconds: float = 60.0
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None


class LLMStreamChunk(BaseModel):
    type: str = "token"  # "token", "reasoning", "tool_call", "usage", "done", "error"
    content: str = ""
    tool_calls: Optional[List[ToolCall]] = None
    finish_reason: Optional[str] = None
    usage: Optional[LLMUsage] = None
    resolved_model: Optional[str] = None
    routing_reason: Optional[str] = None
    citations: Optional[List[Dict[str, Any]]] = None


class LLMResponse(BaseModel):
    content: str = ""
    reasoning_content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    model: str = ""
    finish_reason: str = "stop"
    usage: LLMUsage = Field(default_factory=LLMUsage)
    structured_output: Optional[Any] = None
    citations: Optional[List[Dict[str, Any]]] = None


class ProviderHealth(BaseModel):
    provider: str
    status: str = "offline"  # "online", "degraded", "offline"
    latency_ms: float = 0.0
    models: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class BaseLLMProvider(ABC):
    """Abstract base class for all AI LLM providers in NEXORA AI."""

    @abstractmethod
    async def stream_chat(
        self,
        messages_or_request: Union[List[LLMMessage], LLMRequest],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        reasoning_mode: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout_seconds: float = 60.0
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """Stream response tokens and reasoning chunks asynchronously."""
        yield LLMStreamChunk(type="error", content="Not implemented")

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Non-streaming generation with structured output and tool execution."""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """Ping provider and return health status, latency, and available models."""
        raise NotImplementedError

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if required API keys / credentials are provided."""
        return False
