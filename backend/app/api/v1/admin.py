"""
NEXORA Administration Control Center REST API.
Strictly gated by `require_admin` (`user.role == "admin"`).
Provides real telemetry, user/RBAC management, plan pricing & quota configuration,
model catalog & checkpoint publishing, provider health, security audit logs, and system health.
"""
import json
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.config import settings
from app.core.database import cache, get_db
from app.lab.checkpoints.manager import CheckpointManager
from app.lab.inference.server import InferenceDeploymentManager
from app.lab.telemetry.monitor import HardwareTelemetryMonitor
from app.models.agent import AgentWorkflow
from app.models.audit import AuditLog
from app.models.ecosystem import (
    ApiUsageLog,
    BillingInvoice,
    DeveloperApiKey,
    PublishedModel,
    SecurityEvent,
    SubscriptionPlan,
    UserSubscription,
)
from app.models.lab import LabCheckpoint, LabInferenceDeployment, LabTrainingJob
from app.models.tool_execution import ToolExecution
from app.models.user import User
from app.services.billing_service import billing_service
from app.services.llm.gateway import gateway
from app.services.model_registry.registry import ModelStatus, model_registry
from app.services.storage.object_storage import object_storage

router = APIRouter(
    prefix="/admin",
    tags=["Administration Control Center"],
    dependencies=[Depends(require_admin)],
)


class AdminUserUpdateRequest(BaseModel):
    role: Optional[str] = None  # user, researcher, admin
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    plan_tier: Optional[str] = None  # free, pro, enterprise


class AdminPlanUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    monthly_price_usd: Optional[float] = None
    annual_price_usd: Optional[float] = None
    monthly_token_quota: Optional[int] = None
    rate_limit_rpm: Optional[int] = None
    max_file_size_mb: Optional[int] = None
    api_access_enabled: Optional[bool] = None
    allowed_models: Optional[List[str]] = None
    is_active: Optional[bool] = None


class AdminModelUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    input_price_per_million: Optional[float] = None
    output_price_per_million: Optional[float] = None
    min_plan_tier: Optional[str] = None
    is_enabled: Optional[bool] = None


class AdminPublishCheckpointRequest(BaseModel):
    checkpoint_id: str
    model_id: str
    display_name: str
    description: str = "Admin-published NEXORA proprietary model"
    min_plan_tier: str = "free"
    input_price_per_million: float = 0.50
    output_price_per_million: float = 1.50


@router.get("/overview")
async def admin_overview(db: AsyncSession = Depends(get_db)):
    """Executive KPI summary across commercial usage, revenue, Lab infra, and security."""
    await billing_service.ensure_default_plans(db)

    user_count = int((await db.execute(select(func.count(User.id)))).scalar() or 0)
    active_user_count = int((await db.execute(select(func.count(User.id)).where(User.is_active.is_(True)))).scalar() or 0)
    paid_invoices_sum = float(
        (await db.execute(select(func.coalesce(func.sum(BillingInvoice.amount_usd), 0.0)).where(BillingInvoice.status == "paid"))).scalar()
        or 0.0
    )
    api_stats = (
        await db.execute(
            select(
                func.count(ApiUsageLog.id),
                func.coalesce(func.sum(ApiUsageLog.total_tokens), 0),
                func.coalesce(func.sum(ApiUsageLog.cost_usd), 0.0),
                func.coalesce(func.avg(ApiUsageLog.latency_ms), 0.0),
            )
        )
    ).one()
    error_count = int(
        (await db.execute(select(func.count(ApiUsageLog.id)).where(ApiUsageLog.status_code >= 400))).scalar() or 0
    )
    sec_events_count = int((await db.execute(select(func.count(SecurityEvent.id)))).scalar() or 0)
    active_keys_count = int(
        (await db.execute(select(func.count(DeveloperApiKey.id)).where(DeveloperApiKey.is_revoked.is_(False)))).scalar() or 0
    )
    running_jobs = int(
        (await db.execute(select(func.count(LabTrainingJob.id)).where(LabTrainingJob.status == "running"))).scalar() or 0
    )
    healthy_deps = int(
        (await db.execute(select(func.count(LabInferenceDeployment.id)).where(LabInferenceDeployment.status == "healthy"))).scalar()
        or 0
    )

    hw = HardwareTelemetryMonitor.get_system_telemetry()

    return {
        "users": {"total": user_count, "active": active_user_count},
        "billing": {"total_revenue_usd": round(paid_invoices_sum, 2)},
        "api": {
            "total_requests": int(api_stats[0] or 0),
            "total_tokens": int(api_stats[1] or 0),
            "estimated_inference_cost_usd": round(float(api_stats[2] or 0.0), 4),
            "avg_latency_ms": round(float(api_stats[3] or 0.0), 2),
            "error_count": error_count,
            "active_api_keys": active_keys_count,
        },
        "lab": {
            "running_training_jobs": running_jobs,
            "healthy_deployments": healthy_deps,
            "accelerator": hw["accelerator"],
            "gpu_available": hw["gpu_available"],
        },
        "security": {"total_security_events": sec_events_count},
    }


@router.get("/users")
async def admin_list_users(db: AsyncSession = Depends(get_db)):
    """List platform users with RBAC role and subscription status."""
    await billing_service.ensure_default_plans(db)
    u_res = await db.execute(select(User).order_by(desc(User.created_at)))
    users = u_res.scalars().all()

    sub_res = await db.execute(select(UserSubscription, SubscriptionPlan).join(SubscriptionPlan))
    sub_map: Dict[str, Dict[str, Any]] = {}
    for sub, plan in sub_res.all():
        sub_map[sub.user_id] = {
            "plan_tier": plan.tier,
            "plan_name": plan.name,
            "tokens_used_period": sub.tokens_used_period,
            "status": sub.status,
        }

    return [
        {
            "id": u.id,
            "email": u.email,
            "username": u.username,
            "role": u.role,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "created_at": u.created_at,
            "subscription": sub_map.get(u.id, {"plan_tier": "free", "plan_name": "NEXORA Free", "tokens_used_period": 0, "status": "active"}),
        }
        for u in users
    ]


@router.patch("/users/{user_id}")
async def admin_update_user(
    user_id: str,
    payload: AdminUserUpdateRequest,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update user role, active status, verification status, or subscription tier."""
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.role is not None:
        if payload.role not in ("user", "researcher", "admin"):
            raise HTTPException(status_code=400, detail="Role must be 'user', 'researcher', or 'admin'")
        target.role = payload.role
    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.is_verified is not None:
        target.is_verified = payload.is_verified

    if payload.plan_tier is not None:
        await billing_service.change_plan(
            db=db,
            user=target,
            target_tier=payload.plan_tier,
            billing_cycle="monthly",
            payment_method_summary="Admin Tier Assignment",
        )

    db.add(
        AuditLog(
            user_id=admin_user.id,
            action="admin_user_updated",
            resource_type="user",
            resource_id=target.id,
            ip_address=request.client.host if request.client else None,
            details=json.dumps(payload.model_dump(exclude_none=True)),
        )
    )
    await db.commit()
    await db.refresh(target)
    return {
        "id": target.id,
        "email": target.email,
        "role": target.role,
        "is_active": target.is_active,
        "is_verified": target.is_verified,
    }


@router.get("/plans")
async def admin_list_plans(db: AsyncSession = Depends(get_db)):
    plans = await billing_service.ensure_default_plans(db)
    await db.commit()
    return plans


@router.patch("/plans/{plan_id}")
async def admin_update_plan(
    plan_id: str,
    payload: AdminPlanUpdateRequest,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Dynamically reconfigure subscription pricing, quotas, RPM, and model access."""
    await billing_service.ensure_default_plans(db)
    plan = await db.get(SubscriptionPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")

    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(plan, field, val)

    db.add(
        AuditLog(
            user_id=admin_user.id,
            action="admin_plan_updated",
            resource_type="subscription_plan",
            resource_id=plan.id,
            ip_address=request.client.host if request.client else None,
            details=json.dumps(payload.model_dump(exclude_none=True)),
        )
    )
    await db.commit()
    await db.refresh(plan)
    return plan


@router.get("/models")
async def admin_list_models(db: AsyncSession = Depends(get_db)):
    """List complete ModelRegistry + PublishedModel catalog including disabled models."""
    pub_res = await db.execute(select(PublishedModel))
    pub_rows = list(pub_res.scalars().all())
    if pub_rows:
        model_registry.sync_published_models(pub_rows)

    pub_map = {r.id: r for r in pub_rows}
    models = model_registry.list_models(include_inactive=True)
    return [
        {
            "id": m.id,
            "display_name": m.name,
            "provider": m.provider.value,
            "version": m.version,
            "description": m.description,
            "context_window": m.context_window,
            "input_price_per_million": m.pricing.input_per_million,
            "output_price_per_million": m.pricing.output_per_million,
            "min_plan_tier": m.min_plan_tier,
            "is_proprietary": m.is_proprietary,
            "is_enabled": m.status == ModelStatus.ACTIVE,
            "checkpoint_id": m.checkpoint_id,
            "approval_status": pub_map[m.id].approval_status if m.id in pub_map else "approved",
        }
        for m in models
    ]


@router.patch("/models/{model_id}")
async def admin_update_model(
    model_id: str,
    payload: AdminModelUpdateRequest,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Enable/disable a model, adjust pricing, or change minimum plan tier live."""
    desc = model_registry.get_model(model_id)
    pub = await db.get(PublishedModel, model_id)
    if not desc and not pub:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    if not pub and desc:
        pub = PublishedModel(
            id=desc.id,
            display_name=desc.name,
            description=desc.description,
            provider=desc.provider.value,
            version=desc.version,
            checkpoint_id=desc.checkpoint_id,
            deployment_alias=desc.deployment_alias,
            context_window=desc.context_window,
            max_output_tokens=desc.max_output_tokens,
            input_price_per_million=desc.pricing.input_per_million,
            output_price_per_million=desc.pricing.output_per_million,
            supports_vision=desc.capabilities.vision,
            supports_reasoning=desc.capabilities.reasoning,
            min_plan_tier=desc.min_plan_tier,
            is_enabled=(desc.status == ModelStatus.ACTIVE),
            is_proprietary=desc.is_proprietary,
            approval_status="approved",
        )
        db.add(pub)

    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(pub, field, val)

    db.add(
        AuditLog(
            user_id=admin_user.id,
            action="admin_model_updated",
            resource_type="published_model",
            resource_id=pub.id,
            ip_address=request.client.host if request.client else None,
            details=json.dumps(payload.model_dump(exclude_none=True)),
        )
    )
    await db.commit()
    await db.refresh(pub)
    model_registry.sync_published_models([pub])
    return pub


@router.post("/models/publish-checkpoint", status_code=status.HTTP_201_CREATED)
async def admin_publish_checkpoint(
    payload: AdminPublishCheckpointRequest,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Validate and promote a NEXORA Model Lab checkpoint into production ModelRegistry."""
    ckpt = await db.get(LabCheckpoint, payload.checkpoint_id)
    if not ckpt:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    val_report = CheckpointManager.validate_checkpoint(ckpt.storage_path, expected_sha256=ckpt.weights_sha256 or None)
    if not val_report.get("validated"):
        raise HTTPException(status_code=400, detail=f"Checkpoint failed validation: {val_report.get('error')}")

    ckpt.validated = True
    ckpt.validation_report = val_report

    pub = await db.get(PublishedModel, payload.model_id)
    if pub:
        pub.display_name = payload.display_name
        pub.description = payload.description
        pub.checkpoint_id = ckpt.id
        pub.deployment_alias = payload.model_id
        pub.min_plan_tier = payload.min_plan_tier
        pub.input_price_per_million = payload.input_price_per_million
        pub.output_price_per_million = payload.output_price_per_million
        pub.is_enabled = True
        pub.is_proprietary = True
        pub.approval_status = "approved"
    else:
        pub = PublishedModel(
            id=payload.model_id,
            display_name=payload.display_name,
            description=payload.description,
            provider="nexora",
            version=ckpt.version,
            checkpoint_id=ckpt.id,
            deployment_alias=payload.model_id,
            min_plan_tier=payload.min_plan_tier,
            input_price_per_million=payload.input_price_per_million,
            output_price_per_million=payload.output_price_per_million,
            is_enabled=True,
            is_proprietary=True,
            approval_status="approved",
        )
        db.add(pub)

    db.add(
        AuditLog(
            user_id=admin_user.id,
            action="admin_checkpoint_published",
            resource_type="published_model",
            resource_id=payload.model_id,
            ip_address=request.client.host if request.client else None,
            details=json.dumps({"checkpoint_id": ckpt.id}),
        )
    )
    await db.commit()
    await db.refresh(pub)
    model_registry.sync_published_models([pub], checkpoint_paths={ckpt.id: ckpt.storage_path})
    return pub


@router.get("/providers")
async def admin_providers_health():
    """Inspect live Gateway provider health & credential presence (secrets remain masked)."""
    health = await gateway.check_all_health()
    return {
        "providers": {k: v.model_dump() for k, v in health.items()},
        "credential_status": {
            "openai_configured": bool(settings.OPENAI_API_KEY),
            "gemini_configured": bool(settings.GEMINI_API_KEY),
            "anthropic_configured": bool(settings.ANTHROPIC_API_KEY),
            "huggingface_configured": bool(settings.HUGGINGFACE_API_KEY),
            "openai_compatible_configured": bool(settings.OPENAI_COMPATIBLE_BASE_URL),
            "nexora_proprietary": True,
        },
    }


@router.get("/analytics")
async def admin_usage_analytics(db: AsyncSession = Depends(get_db)):
    """Per-model token/cost/latency breakdown plus recent API errors."""
    model_rows = (
        await db.execute(
            select(
                ApiUsageLog.model,
                ApiUsageLog.provider,
                func.count(ApiUsageLog.id),
                func.coalesce(func.sum(ApiUsageLog.total_tokens), 0),
                func.coalesce(func.sum(ApiUsageLog.cost_usd), 0.0),
                func.coalesce(func.avg(ApiUsageLog.latency_ms), 0.0),
            )
            .group_by(ApiUsageLog.model, ApiUsageLog.provider)
            .order_by(desc(func.count(ApiUsageLog.id)))
        )
    ).all()

    errors_res = await db.execute(
        select(ApiUsageLog)
        .where((ApiUsageLog.status_code >= 400) | (ApiUsageLog.error_message.isnot(None)))
        .order_by(desc(ApiUsageLog.created_at))
        .limit(30)
    )

    return {
        "by_model": [
            {
                "model": r[0] or "unknown",
                "provider": r[1] or "unknown",
                "requests": int(r[2] or 0),
                "total_tokens": int(r[3] or 0),
                "cost_usd": round(float(r[4] or 0.0), 6),
                "avg_latency_ms": round(float(r[5] or 0.0), 2),
            }
            for r in model_rows
        ],
        "recent_errors": [
            {
                "id": e.id,
                "endpoint": e.endpoint,
                "status_code": e.status_code,
                "model": e.model,
                "error_message": e.error_message,
                "created_at": e.created_at,
            }
            for e in errors_res.scalars().all()
        ],
    }


@router.get("/training-and-gpu")
async def admin_training_and_gpu(db: AsyncSession = Depends(get_db)):
    """Real hardware telemetry, active training jobs, and serving deployments."""
    jobs = (await db.execute(select(LabTrainingJob).order_by(desc(LabTrainingJob.created_at)).limit(25))).scalars().all()
    deployments = (await db.execute(select(LabInferenceDeployment).order_by(desc(LabInferenceDeployment.created_at)).limit(25))).scalars().all()
    return {
        "hardware": HardwareTelemetryMonitor.get_system_telemetry(),
        "engines": InferenceDeploymentManager.check_engine_capabilities(),
        "training_jobs": [
            {
                "id": j.id,
                "name": j.name,
                "training_method": j.training_method,
                "framework": j.framework,
                "status": j.status,
                "device_type": j.device_type,
                "current_step": j.current_step,
                "total_steps": j.total_steps,
                "tokens_per_sec": j.tokens_per_sec,
                "current_train_loss": j.current_train_loss,
                "created_at": j.created_at,
            }
            for j in jobs
        ],
        "deployments": [
            {
                "id": d.id,
                "model_alias": d.model_alias,
                "engine": d.engine,
                "quantization": d.quantization,
                "status": d.status,
                "requests_served": d.requests_served,
                "avg_latency_ms": d.avg_latency_ms,
            }
            for d in deployments
        ],
    }


@router.get("/agent-activity")
async def admin_agent_activity(db: AsyncSession = Depends(get_db)):
    workflows = (await db.execute(select(AgentWorkflow).order_by(desc(AgentWorkflow.created_at)).limit(25))).scalars().all()
    tools = (await db.execute(select(ToolExecution).order_by(desc(ToolExecution.created_at)).limit(30))).scalars().all()
    return {
        "workflows": [
            {
                "id": w.id,
                "user_id": w.user_id,
                "goal": w.goal[:120],
                "status": w.status,
                "created_at": w.created_at,
            }
            for w in workflows
        ],
        "tool_executions": [
            {
                "id": t.id,
                "user_id": t.user_id,
                "tool_name": t.tool_name,
                "status": t.status,
                "execution_time_ms": t.execution_time_ms,
                "created_at": t.created_at,
            }
            for t in tools
        ],
    }


@router.get("/security-events")
async def admin_security_events(db: AsyncSession = Depends(get_db)):
    events = (await db.execute(select(SecurityEvent).order_by(desc(SecurityEvent.created_at)).limit(100))).scalars().all()
    return events


@router.get("/audit-logs")
async def admin_audit_logs(db: AsyncSession = Depends(get_db)):
    logs = (await db.execute(select(AuditLog).order_by(desc(AuditLog.created_at)).limit(100))).scalars().all()
    return logs


@router.get("/system-health")
async def admin_system_health(db: AsyncSession = Depends(get_db)):
    """Deep health check across Database, Redis/Cache, Object Storage, and LLM Gateway."""
    t0 = time.perf_counter()
    db_ok = True
    db_error = None
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        db_ok = False
        db_error = str(exc)
    db_latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    redis_ok = False
    if cache._redis is not None:
        try:
            await cache._redis.ping()
            redis_ok = True
        except Exception:
            redis_ok = False

    storage_info = object_storage.health_check()
    hw = HardwareTelemetryMonitor.get_system_telemetry()

    return {
        "overall_status": "healthy" if db_ok else "degraded",
        "environment": settings.ENVIRONMENT,
        "database": {"connected": db_ok, "latency_ms": db_latency_ms, "error": db_error},
        "cache": {"backend": "redis" if redis_ok else "memory_fallback", "redis_connected": redis_ok},
        "storage": storage_info,
        "hardware": {
            "accelerator": hw["accelerator"],
            "cpu_utilization_pct": hw["cpu"]["utilization_pct"],
            "ram_used_pct": hw["memory"]["ram_utilization_pct"],
        },
    }
