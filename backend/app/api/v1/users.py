from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import hash_password, verify_password
from app.models.agent import AgentWorkflow
from app.models.attachment import Attachment
from app.models.audit import AuditLog
from app.models.ecosystem import (
    BillingInvoice,
    DeveloperApiKey,
    UserSubscription,
)
from app.models.feedback import Feedback
from app.models.media_job import MediaJob
from app.models.memory import Memory
from app.models.preference import UserPreference
from app.models.profile import Profile
from app.models.rag import KnowledgeCollection
from app.models.tool_execution import ToolExecution
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.user import (
    PasswordChangeRequest,
    PreferenceResponse,
    PreferenceUpdateRequest,
    ProfileResponse,
    ProfileUpdateRequest,
    UserResponse,
)
from app.services.storage.object_storage import object_storage

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_my_account(
    current_user: User = Depends(get_current_user),
):
    """Get the current authenticated user's profile and preferences."""
    return current_user


@router.put("/me/profile", response_model=ProfileResponse)
async def update_my_profile(
    data: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update profile details for the current user."""
    profile = current_user.profile
    if not profile:
        profile = Profile(user_id=current_user.id)
        db.add(profile)

    update_dict = data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return profile


@router.put("/me/preferences", response_model=PreferenceResponse)
async def update_my_preferences(
    data: PreferenceUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update UI and LLM preferences for current user."""
    prefs = current_user.preferences
    if not prefs:
        prefs = UserPreference(user_id=current_user.id)
        db.add(prefs)

    update_dict = data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(prefs, field, value)

    await db.commit()
    await db.refresh(prefs)
    return prefs


@router.post("/me/change-password", response_model=MessageResponse)
async def change_password(
    data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change current user password."""
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.hashed_password = hash_password(data.new_password)
    await db.commit()
    return MessageResponse(message="Password changed successfully")


@router.delete("/me", response_model=MessageResponse)
async def delete_my_account(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    GDPR Right-to-Erasure: permanently purge user account, uploaded files,
    conversations, memories, RAG collections, API keys, and billing subscription.
    """
    user_id = current_user.id

    # 1. Remove physical uploaded attachments safely
    att_res = await db.execute(select(Attachment).where(Attachment.user_id == user_id))
    for att in att_res.scalars().all():
        object_storage.delete_object(att.storage_path)

    # 2. Explicit cross-table purge (ensures full deletion even on SQLite without cascade PRAGMA)
    for model_cls in (
        Attachment,
        Feedback,
        Memory,
        KnowledgeCollection,
        AgentWorkflow,
        ToolExecution,
        MediaJob,
        DeveloperApiKey,
        BillingInvoice,
        UserSubscription,
    ):
        await db.execute(delete(model_cls).where(model_cls.user_id == user_id))

    # 3. Record anonymized compliance audit entry
    db.add(
        AuditLog(
            user_id=None,
            action="gdpr_account_deleted",
            resource_type="user",
            resource_id=user_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            details='{"reason": "user_requested_erasure"}',
        )
    )

    user_obj = await db.get(User, user_id)
    if user_obj:
        await db.delete(user_obj)
    await db.commit()
    return MessageResponse(message="Your account and associated personal data have been permanently deleted.")
