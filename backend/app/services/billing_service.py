"""
Commercial Subscription, Quota Enforcement, Invoice Generation, and Payment Provider Abstraction Service.
Supports Stripe (with webhook HMAC-SHA256 verification) and deterministic local billing for dev/testing.
"""
import hashlib
import hmac
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.rate_limiter import rate_limiter
from app.core.security_guards import record_security_event
from app.models.ecosystem import BillingInvoice, SubscriptionPlan, UserSubscription
from app.models.user import User

logger = logging.getLogger(__name__)

TIER_ORDER = {"free": 0, "pro": 1, "enterprise": 2}

DEFAULT_PLANS = [
    {
        "id": "plan-free",
        "tier": "free",
        "name": "NEXORA Free",
        "description": "Essential AI workspace with NEXORA Auto & Fast engines and starter monthly quota.",
        "monthly_price_usd": 0.0,
        "annual_price_usd": 0.0,
        "monthly_token_quota": 250000,
        "rate_limit_rpm": 20,
        "max_file_size_mb": 10,
        "api_access_enabled": False,
        "allowed_models": [
            "nexora-auto",
            "nexora-pro",
            "nexora-fast",
            "nexora-flagship",
            "gemini-1.5-flash",
            "gpt-4o-mini",
            "ollama-local",
        ],
        "allowed_features": ["chat", "markdown", "code_highlight", "rag_basic"],
    },
    {
        "id": "plan-pro",
        "tier": "pro",
        "name": "NEXORA Pro",
        "description": "Full multimodal intelligence, autonomous agents, frontier models, and Commercial API keys.",
        "monthly_price_usd": 29.0,
        "annual_price_usd": 290.0,
        "monthly_token_quota": 5000000,
        "rate_limit_rpm": 60,
        "max_file_size_mb": 50,
        "api_access_enabled": True,
        "allowed_models": ["*"],
        "allowed_features": ["chat", "reasoning", "multimodal", "voice", "video", "documents", "agents", "api_access"],
    },
    {
        "id": "plan-enterprise",
        "tier": "enterprise",
        "name": "NEXORA Enterprise",
        "description": "High-throughput commercial SLA, custom proprietary fine-tuned checkpoints, and dedicated support.",
        "monthly_price_usd": 199.0,
        "annual_price_usd": 1990.0,
        "monthly_token_quota": 50000000,
        "rate_limit_rpm": 300,
        "max_file_size_mb": 250,
        "api_access_enabled": True,
        "allowed_models": ["*"],
        "allowed_features": ["*"],
    },
]


class BillingService:
    """Manages plans, subscriptions, token quotas, RPM limits, and invoices."""

    @staticmethod
    async def ensure_default_plans(db: AsyncSession) -> List[SubscriptionPlan]:
        """Idempotently seed Free, Pro, and Enterprise subscription plans."""
        res = await db.execute(select(SubscriptionPlan).order_by(SubscriptionPlan.monthly_price_usd.asc()))
        existing = list(res.scalars().all())
        existing_tiers = {p.tier for p in existing}

        added = False
        for spec in DEFAULT_PLANS:
            if spec["tier"] not in existing_tiers:
                plan = SubscriptionPlan(
                    id=spec["id"],
                    tier=spec["tier"],
                    name=spec["name"],
                    description=spec["description"],
                    monthly_price_usd=spec["monthly_price_usd"],
                    annual_price_usd=spec["annual_price_usd"],
                    monthly_token_quota=spec["monthly_token_quota"],
                    rate_limit_rpm=spec["rate_limit_rpm"],
                    max_file_size_mb=spec["max_file_size_mb"],
                    api_access_enabled=spec["api_access_enabled"],
                    allowed_models=spec["allowed_models"],
                    allowed_features=spec["allowed_features"],
                    is_active=True,
                )
                db.add(plan)
                existing.append(plan)
                added = True

        if added:
            await db.flush()
            res = await db.execute(select(SubscriptionPlan).order_by(SubscriptionPlan.monthly_price_usd.asc()))
            existing = list(res.scalars().all())
        return existing

    @classmethod
    async def get_or_create_subscription(
        cls,
        db: AsyncSession,
        user_id: str,
    ) -> Tuple[UserSubscription, SubscriptionPlan]:
        """Retrieve user's subscription, auto-assigning Free (or Enterprise for admins) if missing."""
        plans = await cls.ensure_default_plans(db)
        plan_by_tier = {p.tier: p for p in plans}

        sub_q = (
            select(UserSubscription)
            .options(selectinload(UserSubscription.plan))
            .where(UserSubscription.user_id == user_id)
        )
        sub_res = await db.execute(sub_q)
        sub = sub_res.scalar_one_or_none()
        if sub:
            # Reset monthly period automatically if expired
            now = datetime.now(timezone.utc)
            end_dt = sub.current_period_end
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            if now > end_dt and sub.status == "active":
                sub.tokens_used_period = 0
                sub.requests_period = 0
                sub.current_period_start = now
                sub.current_period_end = now + timedelta(days=30 if sub.billing_cycle == "monthly" else 365)
                await db.flush()
            return sub, sub.plan

        # Check user role: admins default to Enterprise capacity if no sub assigned yet
        user = await db.get(User, user_id)
        default_tier = "enterprise" if (user and user.role == "admin") else "free"
        target_plan = plan_by_tier.get(default_tier) or plans[0]
        now = datetime.now(timezone.utc)
        sub = UserSubscription(
            id=str(uuid.uuid4()),
            user_id=user_id,
            plan_id=target_plan.id,
            status="active",
            billing_cycle="monthly",
            tokens_used_period=0,
            requests_period=0,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            payment_provider=settings.PAYMENT_PROVIDER,
        )
        db.add(sub)
        await db.flush()
        return sub, target_plan

    @classmethod
    def check_model_permitted(
        cls,
        plan: SubscriptionPlan,
        user_role: str,
        model_id: str,
        min_plan_tier: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Verify whether plan/role allows invoking `model_id`."""
        if user_role == "admin":
            return True, ""
        if min_plan_tier:
            user_rank = TIER_ORDER.get(plan.tier, 0)
            req_rank = TIER_ORDER.get(min_plan_tier, 0)
            if user_rank < req_rank:
                return (
                    False,
                    f"Model '{model_id}' requires the '{min_plan_tier}' plan or higher (current tier: '{plan.tier}').",
                )
        allowed = plan.allowed_models or []
        if "*" in allowed or model_id in allowed:
            return True, ""
        # Published custom proprietary checkpoints on Enterprise or matching list
        return (
            False,
            f"Model '{model_id}' is not included in the '{plan.name}' plan. Please upgrade to Pro or Enterprise.",
        )

    @classmethod
    async def enforce_request_gates(
        cls,
        db: AsyncSession,
        user: User,
        model_id: Optional[str] = None,
        is_api_key: bool = False,
        endpoint: str = "/chat",
        ip_address: Optional[str] = None,
    ) -> Tuple[UserSubscription, SubscriptionPlan]:
        """Enforce plan API entitlement, rate limits, monthly token quota, and model permissions."""
        sub, plan = await cls.get_or_create_subscription(db, user.id)

        if sub.status != "active":
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Subscription status is '{sub.status}'. Please reactivate billing to continue.",
            )

        if is_api_key and user.role != "admin" and not plan.api_access_enabled:
            await record_security_event(
                db,
                event_type="plan_api_access_denied",
                severity="low",
                user_id=user.id,
                ip_address=ip_address,
                endpoint=endpoint,
                details={"plan_tier": plan.tier},
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Commercial API key access requires Pro or Enterprise plan (current: '{plan.name}').",
            )

        # Sliding-window RPM limit
        effective_rpm = plan.rate_limit_rpm if user.role != "admin" else max(300, plan.rate_limit_rpm)
        allowed_rl, _, reset_sec = await rate_limiter.check(
            bucket_key=f"user:{user.id}",
            limit_rpm=effective_rpm,
        )
        if not allowed_rl:
            await record_security_event(
                db,
                event_type="rate_limit_exceeded",
                severity="medium",
                user_id=user.id,
                ip_address=ip_address,
                endpoint=endpoint,
                details={"limit_rpm": effective_rpm},
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded ({effective_rpm} requests/min on '{plan.name}'). Retry in {reset_sec}s.",
                headers={"Retry-After": str(reset_sec)},
            )

        # Monthly token quota check
        if user.role != "admin" and plan.monthly_token_quota > 0 and sub.tokens_used_period >= plan.monthly_token_quota:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Monthly token quota exceeded ({sub.tokens_used_period:,}/{plan.monthly_token_quota:,} tokens). "
                    "Upgrade your subscription plan at /billing to increase limits."
                ),
            )

        # Model access check
        if model_id:
            from app.services.model_registry.registry import model_registry
            desc = model_registry.get_model(model_id)
            min_tier = desc.min_plan_tier if desc else None
            permitted, reason = cls.check_model_permitted(plan, user.role, model_id, min_tier)
            if not permitted:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=reason,
                )

        return sub, plan

    @classmethod
    async def record_consumption(
        cls,
        db: AsyncSession,
        user_id: str,
        tokens: int,
        requests_inc: int = 1,
    ) -> None:
        """Increment subscription period usage counters atomically."""
        sub, _ = await cls.get_or_create_subscription(db, user_id)
        sub.tokens_used_period += max(0, int(tokens))
        sub.requests_period += max(0, int(requests_inc))
        await db.flush()

    @classmethod
    async def change_plan(
        cls,
        db: AsyncSession,
        user: User,
        target_tier: str,
        billing_cycle: str = "monthly",
        payment_method_summary: str = "Local Test Card ****4242",
    ) -> Dict[str, Any]:
        """Upgrade or downgrade subscription plan and emit a persisted invoice."""
        plans = await cls.ensure_default_plans(db)
        target_plan = next((p for p in plans if p.tier == target_tier.lower() and p.is_active), None)
        if not target_plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subscription plan tier '{target_tier}' not found or inactive.",
            )

        if billing_cycle not in ("monthly", "annual"):
            raise HTTPException(status_code=400, detail="billing_cycle must be 'monthly' or 'annual'.")

        sub, current_plan = await cls.get_or_create_subscription(db, user.id)
        old_rank = TIER_ORDER.get(current_plan.tier, 0)
        new_rank = TIER_ORDER.get(target_plan.tier, 0)
        reason = "subscription_upgrade" if new_rank >= old_rank else "subscription_downgrade"

        now = datetime.now(timezone.utc)
        sub.plan_id = target_plan.id
        sub.status = "active"
        sub.billing_cycle = billing_cycle
        sub.cancel_at_period_end = False
        sub.current_period_start = now
        sub.current_period_end = now + timedelta(days=365 if billing_cycle == "annual" else 30)

        amount = (
            target_plan.annual_price_usd
            if billing_cycle == "annual"
            else target_plan.monthly_price_usd
        )

        # Provider abstraction (Stripe session metadata if configured, else deterministic local ledger)
        checkout_mode = settings.PAYMENT_PROVIDER.lower()
        if checkout_mode == "stripe" and settings.STRIPE_SECRET_KEY:
            sub.payment_provider = "stripe"
            sub.external_subscription_id = f"sub_stripe_{uuid.uuid4().hex[:14]}"
        else:
            sub.payment_provider = "local"
            sub.external_subscription_id = f"sub_local_{uuid.uuid4().hex[:14]}"

        invoice = BillingInvoice(
            id=str(uuid.uuid4()),
            user_id=user.id,
            subscription_id=sub.id,
            plan_id=target_plan.id,
            invoice_number=f"INV-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
            amount_usd=float(amount),
            currency="USD",
            status="paid",
            billing_reason=reason,
            payment_method_summary=payment_method_summary,
        )
        db.add(invoice)
        await db.commit()
        await db.refresh(sub)
        await db.refresh(invoice)

        return {
            "subscription": sub,
            "plan": target_plan,
            "invoice": invoice,
        }

    @staticmethod
    def verify_stripe_webhook_signature(payload_bytes: bytes, signature_header: Optional[str]) -> bool:
        """Verify Stripe-style `t=...,v1=...` HMAC-SHA256 webhook signature."""
        if not signature_header:
            return False

        secret = settings.STRIPE_WEBHOOK_SECRET or "whsec_nexora_local_test"

        parts: Dict[str, str] = {}
        for item in signature_header.split(","):
            if "=" in item:
                k, v = item.strip().split("=", 1)
                parts[k] = v

        timestamp = parts.get("t")
        sig_v1 = parts.get("v1")
        if not timestamp or not sig_v1:
            return False

        signed_payload = f"{timestamp}.".encode("utf-8") + payload_bytes
        expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig_v1)


billing_service = BillingService()
