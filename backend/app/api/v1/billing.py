from datetime import datetime, timezone
import json
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security_guards import record_security_event
from app.models.audit import AuditLog
from app.models.ecosystem import BillingInvoice
from app.models.user import User
from app.services.billing_service import billing_service

router = APIRouter(prefix="/billing", tags=["Billing & Subscriptions"])


class SubscribeRequest(BaseModel):
    tier: str  # free, pro, enterprise
    billing_cycle: str = "monthly"  # monthly, annual
    payment_method_summary: str = "Local Test Card ****4242"


class CancelSubscriptionRequest(BaseModel):
    immediate: bool = False


@router.get("/plans")
async def list_subscription_plans(db: AsyncSession = Depends(get_db)):
    """List all active commercial subscription plans and quotas."""
    plans = await billing_service.ensure_default_plans(db)
    await db.commit()
    return [p for p in plans if p.is_active]


@router.get("/subscription")
async def get_my_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve current user's active subscription, quota balance, and plan features."""
    sub, plan = await billing_service.get_or_create_subscription(db, current_user.id)
    await db.commit()

    quota = max(1, int(plan.monthly_token_quota))
    used = int(sub.tokens_used_period)
    pct = round(min(100.0, (used / quota) * 100.0), 2)
    return {
        "subscription": {
            "id": sub.id,
            "status": sub.status,
            "billing_cycle": sub.billing_cycle,
            "tokens_used_period": used,
            "requests_period": sub.requests_period,
            "tokens_remaining": max(0, quota - used),
            "quota_utilization_pct": pct,
            "current_period_start": sub.current_period_start,
            "current_period_end": sub.current_period_end,
            "cancel_at_period_end": sub.cancel_at_period_end,
            "payment_provider": sub.payment_provider,
        },
        "plan": {
            "id": plan.id,
            "tier": plan.tier,
            "name": plan.name,
            "description": plan.description,
            "monthly_price_usd": plan.monthly_price_usd,
            "annual_price_usd": plan.annual_price_usd,
            "monthly_token_quota": plan.monthly_token_quota,
            "rate_limit_rpm": plan.rate_limit_rpm,
            "max_file_size_mb": plan.max_file_size_mb,
            "api_access_enabled": plan.api_access_enabled,
            "allowed_models": plan.allowed_models,
            "allowed_features": plan.allowed_features,
        },
    }


@router.post("/subscribe")
async def change_subscription_plan(
    payload: SubscribeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upgrade or downgrade user subscription tier and emit billing invoice."""
    res = await billing_service.change_plan(
        db=db,
        user=current_user,
        target_tier=payload.tier,
        billing_cycle=payload.billing_cycle,
        payment_method_summary=payload.payment_method_summary,
    )
    sub = res["subscription"]
    plan = res["plan"]
    invoice = res["invoice"]

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="subscription_plan_changed",
            resource_type="subscription",
            resource_id=sub.id,
            ip_address=request.client.host if request.client else None,
            details=json.dumps({"tier": plan.tier, "amount_usd": invoice.amount_usd}),
        )
    )
    await db.commit()

    return {
        "success": True,
        "message": f"Subscription updated cleanly to {plan.name} ({sub.billing_cycle}).",
        "subscription": {
            "id": sub.id,
            "status": sub.status,
            "billing_cycle": sub.billing_cycle,
            "payment_provider": sub.payment_provider,
            "current_period_end": sub.current_period_end,
        },
        "plan": {
            "id": plan.id,
            "tier": plan.tier,
            "name": plan.name,
            "monthly_token_quota": plan.monthly_token_quota,
            "rate_limit_rpm": plan.rate_limit_rpm,
            "api_access_enabled": plan.api_access_enabled,
        },
        "invoice": {
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "amount_usd": invoice.amount_usd,
            "currency": invoice.currency,
            "status": invoice.status,
            "billing_reason": invoice.billing_reason,
            "created_at": invoice.created_at,
        },
    }


@router.post("/cancel")
async def cancel_subscription(
    payload: CancelSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Schedule end-of-period cancellation or immediately downgrade to Free tier."""
    if payload.immediate:
        res = await billing_service.change_plan(
            db=db,
            user=current_user,
            target_tier="free",
            billing_cycle="monthly",
            payment_method_summary="Cancelled / Downgraded to Free",
        )
        return {
            "success": True,
            "message": "Subscription downgraded immediately to Free tier.",
            "tier": res["plan"].tier,
        }

    sub, plan = await billing_service.get_or_create_subscription(db, current_user.id)
    sub.cancel_at_period_end = True
    await db.commit()
    return {
        "success": True,
        "message": f"Subscription '{plan.name}' marked to cancel at period end.",
        "cancel_at_period_end": True,
        "current_period_end": sub.current_period_end,
    }


@router.get("/invoices")
async def list_my_invoices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List current user's commercial invoices and payment receipts."""
    res = await db.execute(
        select(BillingInvoice)
        .where(BillingInvoice.user_id == current_user.id)
        .order_by(desc(BillingInvoice.created_at))
    )
    return res.scalars().all()


@router.post("/webhook")
async def stripe_billing_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(default=None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
):
    """Verified Stripe-compatible payment webhook handler with HMAC-SHA256 check."""
    body = await request.body()
    if not billing_service.verify_stripe_webhook_signature(body, stripe_signature):
        await record_security_event(
            db,
            event_type="invalid_webhook_signature",
            severity="high",
            ip_address=request.client.host if request.client else None,
            endpoint="/api/v1/billing/webhook",
        )
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature.")

    try:
        event = json.loads(body.decode("utf-8") or "{}")
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed webhook JSON payload.")

    return {
        "received": True,
        "event_type": event.get("type", "ping"),
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
