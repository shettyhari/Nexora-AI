import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_action_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_action_token,
    verify_password
)
from app.models.audit import AuditLog
from app.models.preference import UserPreference
from app.models.profile import Profile
from app.models.user import User
from app.schemas.auth import (
    EmailVerifyRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest
)
from app.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user account with profile and preferences."""
    # Check if email or username already exists
    existing = await db.execute(
        select(User).where(or_(User.email == data.email.lower(), User.username == data.username.lower()))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists"
        )

    # Hash password
    hashed_pwd = hash_password(data.password)

    # Create User
    new_user = User(
        email=data.email.lower(),
        username=data.username.lower(),
        hashed_password=hashed_pwd,
        is_active=True,
        is_verified=False
    )
    db.add(new_user)
    await db.flush()

    # Create Profile
    new_profile = Profile(
        user_id=new_user.id,
        display_name=data.display_name or data.username
    )
    db.add(new_profile)

    # Create Default Preferences
    new_prefs = UserPreference(
        user_id=new_user.id,
        theme="system",
        default_model=settings.DEFAULT_MODEL_ID,
        stream_responses=True,
        enter_to_send=True
    )
    db.add(new_prefs)

    # Audit Log
    audit = AuditLog(
        user_id=new_user.id,
        action="register",
        resource_type="user",
        resource_id=new_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db.add(audit)
    await db.commit()

    # Create Tokens
    access_token = create_access_token(new_user.id)
    refresh_token = create_refresh_token(new_user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    data: UserLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate with email or username and password."""
    login_id = data.login.lower().strip()
    query = (
        select(User)
        .options(selectinload(User.profile), selectinload(User.preferences))
        .where(or_(User.email == login_id, User.username == login_id))
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated"
        )

    # Audit Log
    audit = AuditLog(
        user_id=user.id,
        action="login",
        resource_type="user",
        resource_id=user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db.add(audit)
    await db.commit()

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token_endpoint(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """Issue a new access token using a valid refresh token."""
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    user_id = payload.get("sub")
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    new_access_token = create_access_token(user.id)
    new_refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Log out current user and write audit record."""
    audit = AuditLog(
        user_id=current_user.id,
        action="logout",
        resource_type="user",
        resource_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db.add(audit)
    await db.commit()
    return MessageResponse(message="Successfully logged out")


@router.post("/password-reset-request", response_model=MessageResponse)
async def request_password_reset(
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """Generate a password reset token for user."""
    query = select(User).where(User.email == data.email.lower())
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user:
        reset_token = create_action_token(
            subject=user.id,
            action="password_reset",
            expires_hours=settings.RESET_TOKEN_EXPIRE_HOURS
        )
        user.reset_password_token = reset_token
        await db.commit()
        # In production this would send an email. For local/development, we log it.
        logger.info(f"Password reset token for {user.email}: {reset_token}")

    return MessageResponse(
        message="If an account with this email exists, a password reset link has been dispatched."
    )


@router.post("/password-reset-confirm", response_model=MessageResponse)
async def confirm_password_reset(
    data: PasswordResetConfirmRequest,
    db: AsyncSession = Depends(get_db)
):
    """Reset password with token."""
    user_id = verify_action_token(data.token, expected_action="password_reset")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.hashed_password = hash_password(data.new_password)
    user.reset_password_token = None
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return MessageResponse(message="Password reset successfully. You can now log in.")


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    data: EmailVerifyRequest,
    db: AsyncSession = Depends(get_db)
):
    """Verify user email address using token."""
    user_id = verify_action_token(data.token, expected_action="verify_email")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_verified = True
    user.verification_token = None
    await db.commit()

    return MessageResponse(message="Email verified successfully")
