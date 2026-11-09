import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, hash_api_key
from app.core.database import get_db
from app.models.audit import AuditLog
from app.models.ecosystem import ApiUsageLog, DeveloperApiKey
from app.models.user import User
from app.services.billing_service import billing_service

router = APIRouter(prefix="/developer", tags=["Developer Ecosystem"])


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    scopes: List[str] = Field(default_factory=lambda: ["models", "chat", "embeddings"])
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=3650)


def _mint_api_key() -> tuple[str, str, str]:
    """Generate cryptographically secure `nex_live_...` API key, prefix, and SHA-256 hash."""
    raw_secret = secrets.token_urlsafe(32)
    plaintext_key = f"nex_live_{raw_secret}"
    key_prefix = plaintext_key[:16]
    key_hash = hash_api_key(plaintext_key)
    return plaintext_key, key_prefix, key_hash


@router.get("/keys")
async def list_developer_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's API keys safely (plaintext key & SHA-256 hash are never exposed)."""
    res = await db.execute(
        select(DeveloperApiKey)
        .where(DeveloperApiKey.user_id == current_user.id)
        .order_by(desc(DeveloperApiKey.created_at))
    )
    keys = res.scalars().all()
    return [
        {
            "id": k.id,
            "name": k.name,
            "key_prefix": k.key_prefix,
            "masked_key": f"{k.key_prefix}••••••••••••",
            "scopes": k.scopes,
            "is_revoked": k.is_revoked,
            "total_requests": k.total_requests,
            "total_tokens": k.total_tokens,
            "last_used_at": k.last_used_at,
            "expires_at": k.expires_at,
            "created_at": k.created_at,
        }
        for k in keys
    ]


@router.post("/keys", status_code=status.HTTP_201_CREATED)
async def create_developer_key(
    payload: CreateApiKeyRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a cryptographically random `nex_live_` API key.
    Plaintext key is returned ONCE upon creation and only SHA-256 hash is persisted.
    Requires Pro/Enterprise plan or Admin role.
    """
    _, plan = await billing_service.get_or_create_subscription(db, current_user.id)
    if current_user.role != "admin" and not plan.api_access_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API key creation requires Pro or Enterprise subscription (current tier: '{plan.tier}').",
        )

    plaintext_key, key_prefix, key_hash = _mint_api_key()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)
        if payload.expires_in_days
        else None
    )

    api_key = DeveloperApiKey(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=payload.name.strip(),
        key_prefix=key_prefix,
        key_hash=key_hash,
        scopes=payload.scopes,
        rate_limit_rpm=plan.rate_limit_rpm,
        expires_at=expires_at,
    )
    db.add(api_key)
    db.add(
        AuditLog(
            user_id=current_user.id,
            action="api_key_created",
            resource_type="api_key",
            resource_id=api_key.id,
            ip_address=request.client.host if request.client else None,
            details=json.dumps({"name": api_key.name, "key_prefix": key_prefix}),
        )
    )
    await db.commit()
    await db.refresh(api_key)

    return {
        "id": api_key.id,
        "name": api_key.name,
        "key_prefix": api_key.key_prefix,
        "plaintext_key": plaintext_key,
        "scopes": api_key.scopes,
        "rate_limit_rpm": api_key.rate_limit_rpm,
        "expires_at": api_key.expires_at,
        "created_at": api_key.created_at,
        "warning": "Store this secret key securely now — it will never be displayed again.",
    }


@router.post("/keys/{key_id}/revoke")
async def revoke_developer_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Permanently revoke an API key owned by the user."""
    res = await db.execute(
        select(DeveloperApiKey).where(
            DeveloperApiKey.id == key_id,
            DeveloperApiKey.user_id == current_user.id,
        )
    )
    key_obj = res.scalar_one_or_none()
    if not key_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found.")

    key_obj.is_revoked = True
    await db.commit()
    return {"id": key_obj.id, "is_revoked": True, "message": "API key revoked successfully."}


@router.post("/keys/{key_id}/rotate")
async def rotate_developer_key(
    key_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke old key immediately and issue a newly rotated key preserving scopes/name."""
    res = await db.execute(
        select(DeveloperApiKey).where(
            DeveloperApiKey.id == key_id,
            DeveloperApiKey.user_id == current_user.id,
        )
    )
    old_key = res.scalar_one_or_none()
    if not old_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found.")

    old_key.is_revoked = True
    plaintext_key, key_prefix, key_hash = _mint_api_key()
    new_key = DeveloperApiKey(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=old_key.name,
        key_prefix=key_prefix,
        key_hash=key_hash,
        scopes=old_key.scopes,
        rate_limit_rpm=old_key.rate_limit_rpm,
        expires_at=old_key.expires_at,
    )
    db.add(new_key)
    db.add(
        AuditLog(
            user_id=current_user.id,
            action="api_key_rotated",
            resource_type="api_key",
            resource_id=new_key.id,
            ip_address=request.client.host if request.client else None,
            details=json.dumps({"replaced_key_id": old_key.id}),
        )
    )
    await db.commit()
    await db.refresh(new_key)

    return {
        "id": new_key.id,
        "name": new_key.name,
        "key_prefix": new_key.key_prefix,
        "plaintext_key": plaintext_key,
        "rotated_from_key_id": old_key.id,
        "created_at": new_key.created_at,
    }


@router.get("/usage")
async def get_developer_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Inspect user's API consumption, costs, latency, and recent request telemetry."""
    sub, plan = await billing_service.get_or_create_subscription(db, current_user.id)

    agg_res = await db.execute(
        select(
            func.count(ApiUsageLog.id),
            func.coalesce(func.sum(ApiUsageLog.total_tokens), 0),
            func.coalesce(func.sum(ApiUsageLog.cost_usd), 0.0),
            func.coalesce(func.avg(ApiUsageLog.latency_ms), 0.0),
        ).where(ApiUsageLog.user_id == current_user.id)
    )
    total_reqs, total_toks, total_cost, avg_lat = agg_res.one()

    recent_res = await db.execute(
        select(ApiUsageLog)
        .where(ApiUsageLog.user_id == current_user.id)
        .order_by(desc(ApiUsageLog.created_at))
        .limit(50)
    )
    recent_logs = recent_res.scalars().all()

    return {
        "plan_tier": plan.tier,
        "api_access_enabled": plan.api_access_enabled or current_user.role == "admin",
        "rate_limit_rpm": plan.rate_limit_rpm,
        "monthly_token_quota": plan.monthly_token_quota,
        "tokens_used_period": sub.tokens_used_period,
        "summary": {
            "total_requests": int(total_reqs or 0),
            "total_tokens": int(total_toks or 0),
            "total_cost_usd": round(float(total_cost or 0.0), 6),
            "avg_latency_ms": round(float(avg_lat or 0.0), 2),
        },
        "recent_logs": [
            {
                "id": log.id,
                "endpoint": log.endpoint,
                "method": log.method,
                "status_code": log.status_code,
                "model": log.model,
                "provider": log.provider,
                "total_tokens": log.total_tokens,
                "cost_usd": log.cost_usd,
                "latency_ms": round(log.latency_ms, 2),
                "created_at": log.created_at,
            }
            for log in recent_logs
        ],
    }
