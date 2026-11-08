from typing import Optional
from pydantic import BaseModel, ConfigDict


class ModelConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    model_key: str
    display_name: str
    provider: str
    model_name: str
    context_window: int
    max_tokens: int
    supports_vision: bool
    supports_reasoning: bool
    is_enabled: bool
    is_default: bool
    description: Optional[str] = None
    badge: Optional[str] = None
