from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    timezone: str = "UTC"
    language: str = "en"


class ProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None


class PreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    theme: str = "system"
    default_model: str = "nexora-pro"
    stream_responses: bool = True
    enter_to_send: bool = True
    custom_instructions: Optional[str] = None
    reasoning_mode_default: bool = False
    web_search_default: bool = False


class PreferenceUpdateRequest(BaseModel):
    theme: Optional[str] = None
    default_model: Optional[str] = None
    stream_responses: Optional[bool] = None
    enter_to_send: Optional[bool] = None
    custom_instructions: Optional[str] = None
    reasoning_mode_default: Optional[bool] = None
    web_search_default: Optional[bool] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    username: str
    is_active: bool
    is_verified: bool
    role: str
    created_at: datetime
    profile: Optional[ProfileResponse] = None
    preferences: Optional[PreferenceResponse] = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
