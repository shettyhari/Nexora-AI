from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.message import MessageResponse


class ConversationCreateRequest(BaseModel):
    title: Optional[str] = "New Chat"
    model_id: Optional[str] = "nexora-pro"
    project_id: Optional[str] = None
    system_prompt: Optional[str] = None
    reasoning_mode: Optional[bool] = False
    web_search_enabled: Optional[bool] = False


class ConversationUpdateRequest(BaseModel):
    title: Optional[str] = None
    is_pinned: Optional[bool] = None
    is_archived: Optional[bool] = None
    model_id: Optional[str] = None
    system_prompt: Optional[str] = None
    reasoning_mode: Optional[bool] = None
    web_search_enabled: Optional[bool] = None


class ConversationSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    is_pinned: bool
    is_archived: bool
    model_id: str
    project_id: Optional[str] = None
    reasoning_mode: bool = False
    web_search_enabled: bool = False
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    last_message_preview: Optional[str] = None


class ConversationDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    is_pinned: bool
    is_archived: bool
    model_id: str
    project_id: Optional[str] = None
    system_prompt: Optional[str] = None
    reasoning_mode: bool = False
    web_search_enabled: bool = False
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []
