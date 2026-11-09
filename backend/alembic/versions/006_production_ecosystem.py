"""Production Ecosystem: Subscriptions, Invoices, Developer API Keys, Telemetry, Security Events, and Published Models

Revision ID: 006_production_ecosystem
Revises: 005_training_infrastructure
Create Date: 2026-11-09 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "006_production_ecosystem"
down_revision: Union[str, None] = "005_training_infrastructure"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. subscription_plans
    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tier", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("monthly_price_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("annual_price_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("monthly_token_quota", sa.BigInteger(), nullable=False, server_default="100000"),
        sa.Column("rate_limit_rpm", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("max_file_size_mb", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("api_access_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("allowed_models", sa.JSON(), nullable=False),
        sa.Column("allowed_features", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tier"),
    )
    op.create_index("ix_subscription_plans_tier", "subscription_plans", ["tier"])

    # 2. user_subscriptions
    op.create_table(
        "user_subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("billing_cycle", sa.String(length=20), nullable=False, server_default="monthly"),
        sa.Column("tokens_used_period", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("requests_period", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("payment_provider", sa.String(length=30), nullable=False, server_default="local"),
        sa.Column("external_customer_id", sa.String(length=120), nullable=True),
        sa.Column("external_subscription_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_user_subscriptions_plan_id", "user_subscriptions", ["plan_id"])
    op.create_index("ix_user_subscriptions_user_id", "user_subscriptions", ["user_id"])

    # 3. billing_invoices
    op.create_table(
        "billing_invoices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=True),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("invoice_number", sa.String(length=64), nullable=False),
        sa.Column("amount_usd", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="paid"),
        sa.Column("billing_reason", sa.String(length=80), nullable=False, server_default="subscription_upgrade"),
        sa.Column("payment_method_summary", sa.String(length=100), nullable=False, server_default="Local Test Card ****4242"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["subscription_id"], ["user_subscriptions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_number"),
    )
    op.create_index("ix_billing_invoices_user_id", "billing_invoices", ["user_id"])
    op.create_index("ix_billing_invoices_created_at", "billing_invoices", ["created_at"])

    # 4. developer_api_keys
    op.create_table(
        "developer_api_keys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_prefix", sa.String(length=24), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("rate_limit_rpm", sa.Integer(), nullable=True),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("total_requests", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("ix_developer_api_keys_user_id", "developer_api_keys", ["user_id"])
    op.create_index("ix_developer_api_keys_key_hash", "developer_api_keys", ["key_hash"])

    # 5. api_usage_logs
    op.create_table(
        "api_usage_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("api_key_id", sa.String(length=36), nullable=True),
        sa.Column("endpoint", sa.String(length=150), nullable=False),
        sa.Column("method", sa.String(length=12), nullable=False, server_default="POST"),
        sa.Column("status_code", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["api_key_id"], ["developer_api_keys.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_usage_user_created", "api_usage_logs", ["user_id", "created_at"])

    # 6. security_events
    op.create_table(
        "security_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("endpoint", sa.String(length=150), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_security_events_event_type", "security_events", ["event_type"])
    op.create_index("ix_security_events_severity", "security_events", ["severity"])
    op.create_index("ix_security_events_created_at", "security_events", ["created_at"])

    # 7. published_models
    op.create_table(
        "published_models",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="nexora"),
        sa.Column("version", sa.String(length=40), nullable=False, server_default="1.0.0"),
        sa.Column("lab_model_id", sa.String(length=36), nullable=True),
        sa.Column("checkpoint_id", sa.String(length=36), nullable=True),
        sa.Column("deployment_alias", sa.String(length=120), nullable=True),
        sa.Column("context_window", sa.Integer(), nullable=False, server_default="32768"),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False, server_default="4096"),
        sa.Column("input_price_per_million", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("output_price_per_million", sa.Float(), nullable=False, server_default="1.5"),
        sa.Column("supports_vision", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("supports_reasoning", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("min_plan_tier", sa.String(length=30), nullable=False, server_default="free"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_proprietary", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("approval_status", sa.String(length=30), nullable=False, server_default="approved"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["checkpoint_id"], ["lab_checkpoints.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lab_model_id"], ["lab_models.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("published_models")
    op.drop_index("ix_security_events_created_at", table_name="security_events")
    op.drop_index("ix_security_events_severity", table_name="security_events")
    op.drop_index("ix_security_events_event_type", table_name="security_events")
    op.drop_table("security_events")
    op.drop_index("ix_api_usage_user_created", table_name="api_usage_logs")
    op.drop_table("api_usage_logs")
    op.drop_index("ix_developer_api_keys_key_hash", table_name="developer_api_keys")
    op.drop_index("ix_developer_api_keys_user_id", table_name="developer_api_keys")
    op.drop_table("developer_api_keys")
    op.drop_index("ix_billing_invoices_created_at", table_name="billing_invoices")
    op.drop_index("ix_billing_invoices_user_id", table_name="billing_invoices")
    op.drop_table("billing_invoices")
    op.drop_index("ix_user_subscriptions_user_id", table_name="user_subscriptions")
    op.drop_index("ix_user_subscriptions_plan_id", table_name="user_subscriptions")
    op.drop_table("user_subscriptions")
    op.drop_index("ix_subscription_plans_tier", table_name="subscription_plans")
    op.drop_table("subscription_plans")
