"""
Production Ecosystem Database Models:
Subscriptions, Invoices, Developer API Keys, API Usage Telemetry,
Security Events, and Published Proprietary Model Catalog.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class SubscriptionPlan(Base):
    """Commercial subscription tier definitions and dynamic admin-configurable quotas."""
    __tablename__ = "subscription_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tier: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)  # free, pro, enterprise
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    monthly_price_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    annual_price_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    monthly_token_quota: Mapped[int] = mapped_column(BigInteger, default=100000, nullable=False)
    rate_limit_rpm: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    max_file_size_mb: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    api_access_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    allowed_models: Mapped[List[str]] = mapped_column(JSONType, default=list, nullable=False)
    allowed_features: Mapped[List[str]] = mapped_column(JSONType, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class UserSubscription(Base):
    """Active user subscription and billing period consumption ledger."""
    __tablename__ = "user_subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)  # active, canceled, past_due
    billing_cycle: Mapped[str] = mapped_column(String(20), default="monthly", nullable=False)  # monthly, annual

    tokens_used_period: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    requests_period: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    current_period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    current_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(days=30),
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    payment_provider: Mapped[str] = mapped_column(String(30), default="local", nullable=False)
    external_customer_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    external_subscription_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    plan: Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan")


class BillingInvoice(Base):
    """Persisted commercial billing invoices and payment receipts."""
    __tablename__ = "billing_invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subscription_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("user_subscriptions.id", ondelete="SET NULL"), nullable=True
    )
    plan_id: Mapped[str] = mapped_column(String(36), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    amount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="paid", nullable=False)  # paid, pending, failed, refunded
    billing_reason: Mapped[str] = mapped_column(String(80), default="subscription_upgrade", nullable=False)
    payment_method_summary: Mapped[str] = mapped_column(String(100), default="Local Test Card ****4242", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


class DeveloperApiKey(Base):
    """SHA-256 hashed API keys for commercial & OpenAI-compatible inference SDK access."""
    __tablename__ = "developer_api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(24), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    scopes: Mapped[List[str]] = mapped_column(
        JSONType, default=lambda: ["models", "chat", "embeddings"], nullable=False
    )
    rate_limit_rpm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    total_requests: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


class ApiUsageLog(Base):
    """Fine-grained API request, latency, token usage, cost, and error telemetry."""
    __tablename__ = "api_usage_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    api_key_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("developer_api_keys.id", ondelete="SET NULL"), index=True, nullable=True
    )
    endpoint: Mapped[str] = mapped_column(String(150), nullable=False)
    method: Mapped[str] = mapped_column(String(12), default="POST", nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    __table_args__ = (
        Index("ix_api_usage_user_created", "user_id", "created_at"),
    )


class SecurityEvent(Base):
    """Structured security telemetry capturing blocked exploits, unauthorized calls, and SSRF."""
    __tablename__ = "security_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="medium", index=True, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    endpoint: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    details: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


class PublishedModel(Base):
    """
    Production catalog bridge linking approved NEXORA Model Lab checkpoints
    and commercial/external model configurations directly into ModelRegistry & Gateway.
    """
    __tablename__ = "published_models"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="nexora", nullable=False)
    version: Mapped[str] = mapped_column(String(40), default="1.0.0", nullable=False)

    lab_model_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("lab_models.id", ondelete="SET NULL"), nullable=True
    )
    checkpoint_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("lab_checkpoints.id", ondelete="SET NULL"), nullable=True
    )
    deployment_alias: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    context_window: Mapped[int] = mapped_column(Integer, default=32768, nullable=False)
    max_output_tokens: Mapped[int] = mapped_column(Integer, default=4096, nullable=False)
    input_price_per_million: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    output_price_per_million: Mapped[float] = mapped_column(Float, default=1.5, nullable=False)
    supports_vision: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_reasoning: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    min_plan_tier: Mapped[str] = mapped_column(String(30), default="free", nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_proprietary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(30), default="approved", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
