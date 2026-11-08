from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    file_name: str
    file_type: str
    file_size: int
    storage_path: str
    mime_type: str
    created_at: datetime
