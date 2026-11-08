from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.attachment import AttachmentResponse


class MessageCreateRequest(BaseModel):
    conversation_id: Optional[str] = None
    content: str = Field(..., min_length=1)
    model: Optional[str] = None
    reasoning_mode: Optional[bool] = None
    web_search: Optional[bool] = None
    parent_id: Optional[str] = None
    attachment_ids: Optional[List[str]] = None


class MessageEditRequest(BaseModel):
    content: str = Field(..., min_length=1)
    regenerate: bool = True


class MessageFeedbackRequest(BaseModel):
    rating: str = Field(..., pattern=r"^(like|dislike)$")
    comment: Optional[str] = None
    tags: Optional[str] = None


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    message_id: str
    user_id: str
    rating: str
    comment: Optional[str] = None
    created_at: datetime


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: str
    content: str
    reasoning_content: Optional[str] = None
    model: Optional[str] = None
    tokens_used: int = 0
    is_edited: bool = False
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    attachments: List[AttachmentResponse] = []
    feedback: List[FeedbackResponse] = []
