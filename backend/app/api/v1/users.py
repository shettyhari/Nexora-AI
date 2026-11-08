from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import hash_password, verify_password
from app.models.profile import Profile
from app.models.preference import UserPreference
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.user import (
    PasswordChangeRequest,
    PreferenceResponse,
    PreferenceUpdateRequest,
    ProfileResponse,
    ProfileUpdateRequest,
    UserResponse
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_my_account(
    current_user: User = Depends(get_current_user)
):
    """Get the current authenticated user's profile and preferences."""
    return current_user


@router.put("/me/profile", response_model=ProfileResponse)
async def update_my_profile(
    data: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
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
    db: AsyncSession = Depends(get_db)
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
    db: AsyncSession = Depends(get_db)
):
    """Change current user password."""
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    current_user.hashed_password = hash_password(data.new_password)
    await db.commit()
    return MessageResponse(message="Password changed successfully")

