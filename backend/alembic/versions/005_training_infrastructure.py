"""Model training, fine-tuning, GPU infrastructure and inference deployment migration

Revision ID: 005_training_infrastructure
Revises: 004_model_lab
Create Date: 2026-11-09 12:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "005_training_infrastructure"
down_revision: Union[str, None] = "004_model_lab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend lab_checkpoints for versioning, validation, adapters, and rollback
    with op.batch_alter_table("lab_checkpoints") as batch_op:
        batch_op.alter_column("experiment_id", existing_type=sa.String(length=36), nullable=True)
        batch_op.add_column(sa.Column("training_job_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("version", sa.String(length=30), nullable=False, server_default="1.0.0"))
        batch_op.add_column(sa.Column("format", sa.String(length=50), nullable=False, server_default="pytorch"))
        batch_op.add_column(sa.Column("is_adapter_only", sa.Boolean(), nullable=False, server_default="false"))
        batch_op.add_column(sa.Column("adapter_config", sa.JSON(), nullable=False, server_default="{}"))
        batch_op.add_column(sa.Column("validated", sa.Boolean(), nullable=False, server_default="false"))
        batch_op.add_column(sa.Column("validation_report", sa.JSON(), nullable=False, server_default="{}"))
        batch_op.add_column(sa.Column("export_path", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("parent_checkpoint_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("is_active_rollback_target", sa.Boolean(), nullable=False, server_default="false"))
        batch_op.add_column(sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"))
        batch_op.create_index("ix_lab_checkpoints_training_job_id", ["training_job_id"])

    # 2. lab_training_jobs
    op.create_table(
        "lab_training_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("experiment_id", sa.String(length=36), nullable=True),
        sa.Column("base_model_id", sa.String(length=150), nullable=False),
        sa.Column("base_model_name", sa.String(length=150), nullable=False),
        sa.Column("base_model_license", sa.String(length=100), nullable=False, server_default="Apache-2.0"),
        sa.Column("dataset_id", sa.String(length=36), nullable=True),
        sa.Column("dataset_name", sa.String(length=150), nullable=False, server_default="Default Corpus"),
        sa.Column("dataset_license", sa.String(length=100), nullable=False, server_default="Apache-2.0"),
        sa.Column("intended_use", sa.String(length=50), nullable=False, server_default="research"),
        sa.Column("training_method", sa.String(length=50), nullable=False, server_default="sft"),
        sa.Column("framework", sa.String(length=50), nullable=False, server_default="trl"),
        sa.Column("framework_config", sa.JSON(), nullable=False),
        sa.Column("lora_config", sa.JSON(), nullable=False),
        sa.Column("hyperparameters", sa.JSON(), nullable=False),
        sa.Column("license_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("license_report", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="queued"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("worker_pid", sa.Integer(), nullable=True),
        sa.Column("device_type", sa.String(length=50), nullable=False, server_default="cpu"),
        sa.Column("gpu_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_steps", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("tokens_processed", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("tokens_per_sec", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("current_train_loss", sa.Float(), nullable=True),
        sa.Column("current_val_loss", sa.Float(), nullable=True),
        sa.Column("current_lr", sa.Float(), nullable=True),
        sa.Column("loss_history", sa.JSON(), nullable=False),
        sa.Column("hardware_snapshot", sa.JSON(), nullable=False),
        sa.Column("checkpoint_dir", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("log_file_path", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("metrics_file_path", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("state_file_path", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("output_checkpoint_id", sa.String(length=36), nullable=True),
        sa.Column("checkpoint_validated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("recovery_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["dataset_id"], ["lab_datasets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["experiment_id"], ["lab_experiments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_lab_training_jobs_status", "lab_training_jobs", ["status"])

    # 3. lab_benchmark_suites
    op.create_table(
        "lab_benchmark_suites",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False, server_default="1.0.0"),
        sa.Column("candidate_model_name", sa.String(length=150), nullable=False),
        sa.Column("candidate_checkpoint_id", sa.String(length=36), nullable=True),
        sa.Column("baseline_model_name", sa.String(length=150), nullable=False),
        sa.Column("baseline_checkpoint_id", sa.String(length=36), nullable=True),
        sa.Column("dataset_id", sa.String(length=36), nullable=True),
        sa.Column("leakage_checked", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("leakage_overlap_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("leakage_blocked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("leakage_report", sa.JSON(), nullable=False),
        sa.Column("dimension_scores", sa.JSON(), nullable=False),
        sa.Column("baseline_scores", sa.JSON(), nullable=False),
        sa.Column("deltas", sa.JSON(), nullable=False),
        sa.Column("regression_passed", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("regression_failures", sa.JSON(), nullable=False),
        sa.Column("human_ratings", sa.JSON(), nullable=False),
        sa.Column("aggregate_candidate_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("aggregate_baseline_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id")
    )

    # 4. lab_optimization_runs
    op.create_table(
        "lab_optimization_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("checkpoint_id", sa.String(length=36), nullable=True),
        sa.Column("model_name", sa.String(length=150), nullable=False),
        sa.Column("target_precision", sa.String(length=30), nullable=False, server_default="int8_dynamic"),
        sa.Column("batch_size", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("context_length", sa.Integer(), nullable=False, server_default="256"),
        sa.Column("kv_cache_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("original_size_mb", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("optimized_size_mb", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("compression_ratio", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("ttft_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("tokens_per_sec", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("peak_memory_mb", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("context_scaling_results", sa.JSON(), nullable=False),
        sa.Column("batch_scaling_results", sa.JSON(), nullable=False),
        sa.Column("artifact_path", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="completed"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_lab_optimization_runs_checkpoint_id", "lab_optimization_runs", ["checkpoint_id"])

    # 5. lab_inference_deployments
    op.create_table(
        "lab_inference_deployments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("model_alias", sa.String(length=120), nullable=False),
        sa.Column("checkpoint_id", sa.String(length=36), nullable=True),
        sa.Column("model_name", sa.String(length=150), nullable=False),
        sa.Column("engine", sa.String(length=50), nullable=False, server_default="transformers"),
        sa.Column("quantization", sa.String(length=30), nullable=False, server_default="none"),
        sa.Column("device", sa.String(length=30), nullable=False, server_default="cpu"),
        sa.Column("max_model_len", sa.Integer(), nullable=False, server_default="2048"),
        sa.Column("max_concurrent_requests", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("gpu_memory_utilization", sa.Float(), nullable=False, server_default="0.85"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="healthy"),
        sa.Column("requests_served", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("active_queue_depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_prompt_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_completion_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("avg_latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_alias")
    )
    op.create_index("ix_lab_inference_deployments_checkpoint_id", "lab_inference_deployments", ["checkpoint_id"])


def downgrade() -> None:
    op.drop_index("ix_lab_inference_deployments_checkpoint_id", table_name="lab_inference_deployments")
    op.drop_table("lab_inference_deployments")

    op.drop_index("ix_lab_optimization_runs_checkpoint_id", table_name="lab_optimization_runs")
    op.drop_table("lab_optimization_runs")

    op.drop_table("lab_benchmark_suites")

    op.drop_index("ix_lab_training_jobs_status", table_name="lab_training_jobs")
    op.drop_table("lab_training_jobs")

    with op.batch_alter_table("lab_checkpoints") as batch_op:
        batch_op.drop_index("ix_lab_checkpoints_training_job_id")
        batch_op.drop_column("metadata_json")
        batch_op.drop_column("is_active_rollback_target")
        batch_op.drop_column("parent_checkpoint_id")
        batch_op.drop_column("export_path")
        batch_op.drop_column("validation_report")
        batch_op.drop_column("validated")
        batch_op.drop_column("adapter_config")
        batch_op.drop_column("is_adapter_only")
        batch_op.drop_column("format")
        batch_op.drop_column("version")
        batch_op.drop_column("training_job_id")
        batch_op.alter_column("experiment_id", existing_type=sa.String(length=36), nullable=False)

