from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Optional
from fastapi import Depends, Header, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import decode_token
from app.core.security_guards import record_security_event
from app.models.ecosystem import DeveloperApiKey, SubscriptionPlan, UserSubscription
from app.models.user import User

security_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthPrincipal:
    """Unified authenticated principal from JWT or Developer API key (`nex_...`)."""
    user: User
    api_key: Optional[DeveloperApiKey] = None
    subscription: Optional[UserSubscription] = None
    plan: Optional[SubscriptionPlan] = None
    auth_method: str = "jwt"  # "jwt" or "api_key"


def hash_api_key(raw_key: str) -> str:
    """One-way SHA-256 hash used to store and verify developer API keys safely."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate Bearer JWT token and return active current user."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    query = (
        select(User)
        .options(selectinload(User.profile), selectinload(User.preferences))
        .where(User.id == user_id)
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Return user if token is valid, otherwise None without raising 401."""
    if not credentials or not credentials.credentials:
        return None

    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


async def require_admin(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Strict RBAC guard restricting Administrative Control Center to `admin` role."""
    if (current_user.role or "").lower() != "admin":
        await record_security_event(
            db,
            event_type="unauthorized_admin_access",
            severity="high",
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            endpoint=str(request.url.path),
            details={"user_role": current_user.role},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required for this resource.",
        )
    return current_user


async def require_lab_access(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """RBAC guard restricting NEXORA Model Lab infrastructure to `admin` or `researcher` roles."""
    if (current_user.role or "").lower() not in ("admin", "researcher"):
        await record_security_event(
            db,
            event_type="unauthorized_lab_access",
            severity="medium",
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            endpoint=str(request.url.path),
            details={"user_role": current_user.role},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="NEXORA Model Lab requires 'researcher' or 'admin' role.",
        )
    return current_user


async def authenticate_api_principal(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> AuthPrincipal:
    """
    Authenticate `/v1/*` OpenAI-compatible & Developer API requests via:
    1) `nex_...` Developer API Key (`Authorization: Bearer nex_...` or `X-API-Key: nex_...`)
    2) Valid active User JWT (`Authorization: Bearer <jwt>`)
    Enforces key revocation, expiration, plan API access permission, rate limits, and quota.
    """
    from app.services.billing_service import billing_service

    raw_token = x_api_key or (credentials.credentials if credentials else None)
    ip_addr = request.client.host if request.client else None

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials or NEXORA API key (`nex_...`).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Path 1: Developer API Key (`nex_live_...` / `nex_...`)
    if raw_token.startswith("nex_"):
        key_hash = hash_api_key(raw_token)
        k_res = await db.execute(select(DeveloperApiKey).where(DeveloperApiKey.key_hash == key_hash))
        api_key = k_res.scalar_one_or_none()
        if not api_key:
            await record_security_event(
                db,
                event_type="invalid_api_key",
                severity="medium",
                ip_address=ip_addr,
                endpoint=str(request.url.path),
                details={"key_prefix": raw_token[:14]},
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key.",
            )

        if api_key.is_revoked:
            await record_security_event(
                db,
                event_type="revoked_api_key_attempt",
                severity="medium",
                user_id=api_key.user_id,
                ip_address=ip_addr,
                endpoint=str(request.url.path),
                details={"api_key_id": api_key.id},
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This API key has been revoked.",
            )

        if api_key.expires_at:
            exp = api_key.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key has expired.")

        user = await db.get(User, api_key.user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key owner account is inactive.")

        sub, plan = await billing_service.enforce_request_gates(
            db=db,
            user=user,
            model_id=None,
            is_api_key=True,
            endpoint=str(request.url.path),
            ip_address=ip_addr,
        )
        api_key.last_used_at = datetime.now(timezone.utc)
        await db.flush()
        return AuthPrincipal(
            user=user,
            api_key=api_key,
            subscription=sub,
            plan=plan,
            auth_method="api_key",
        )

    # Path 2: Standard User JWT
    user = await get_current_user(credentials, db)
    sub, plan = await billing_service.enforce_request_gates(
        db=db,
        user=user,
        model_id=None,
        is_api_key=False,
        endpoint=str(request.url.path),
        ip_address=ip_addr,
    )
    return AuthPrincipal(
        user=user,
        api_key=None,
        subscription=sub,
        plan=plan,
        auth_method="jwt",
    )
