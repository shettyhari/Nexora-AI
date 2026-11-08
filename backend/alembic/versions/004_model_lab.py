"""Model Lab foundation research schema migration

Revision ID: 004_model_lab
Revises: 003_multimodal_agents
Create Date: 2026-11-09 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004_model_lab"
down_revision: Union[str, None] = "003_multimodal_agents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. lab_models
    op.create_table(
        "lab_models",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False, server_default="0.1.0"),
        sa.Column("model_family", sa.String(length=50), nullable=False, server_default="nano"),
        sa.Column("architecture_type", sa.String(length=50), nullable=False, server_default="decoder-only"),
        sa.Column("parameter_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("base_model", sa.String(length=100), nullable=False, server_default="scratch"),
        sa.Column("license", sa.String(length=100), nullable=False, server_default="Proprietary-Research"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("architecture_config", sa.JSON(), nullable=False),
        sa.Column("training_config", sa.JSON(), nullable=False),
        sa.Column("evaluation_results", sa.JSON(), nullable=False),
        sa.Column("dataset_associations", sa.JSON(), nullable=False),
        sa.Column("deployment_status", sa.String(length=50), nullable=False, server_default="draft"),
        sa.Column("checkpoint_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id")
    )

    # 2. lab_datasets
    op.create_table(
        "lab_datasets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False, server_default="1.0.0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_uri", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("source_type", sa.String(length=50), nullable=False, server_default="upload"),
        sa.Column("license", sa.String(length=100), nullable=False, server_default="Apache-2.0"),
        sa.Column("file_format", sa.String(length=50), nullable=False, server_default="jsonl"),
        sa.Column("raw_size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cleaned_size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("num_samples_raw", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("num_samples_cleaned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("train_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("val_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("test_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("language_distribution", sa.JSON(), nullable=False),
        sa.Column("pii_findings", sa.JSON(), nullable=False),
        sa.Column("cleaning_stats", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ready"),
        sa.Column("storage_path", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id")
    )

    # 3. lab_tokenizers
    op.create_table(
        "lab_tokenizers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False, server_default="1.0.0"),
        sa.Column("algorithm", sa.String(length=50), nullable=False, server_default="bpe"),
        sa.Column("vocab_size", sa.Integer(), nullable=False, server_default="32000"),
        sa.Column("special_tokens", sa.JSON(), nullable=False),
        sa.Column("training_corpus_id", sa.String(length=36), nullable=True),
        sa.Column("vocab_data", sa.JSON(), nullable=False),
        sa.Column("evaluation_metrics", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ready"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["training_corpus_id"], ["lab_datasets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id")
    )

    # 4. lab_experiments
    op.create_table(
        "lab_experiments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("model_id", sa.String(length=36), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("dataset_id", sa.String(length=36), nullable=True),
        sa.Column("dataset_version", sa.String(length=20), nullable=False, server_default="1.0.0"),
        sa.Column("tokenizer_id", sa.String(length=36), nullable=True),
        sa.Column("hyperparameters", sa.JSON(), nullable=False),
        sa.Column("reproducibility_env", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="created"),
        sa.Column("duration_seconds", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_steps", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("best_val_loss", sa.Float(), nullable=True),
        sa.Column("best_perplexity", sa.Float(), nullable=True),
        sa.Column("loss_history", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["dataset_id"], ["lab_datasets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["model_id"], ["lab_models.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )

    # 5. lab_checkpoints
    op.create_table(
        "lab_checkpoints",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("experiment_id", sa.String(length=36), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("train_loss", sa.Float(), nullable=False),
        sa.Column("val_loss", sa.Float(), nullable=False),
        sa.Column("perplexity", sa.Float(), nullable=False),
        sa.Column("learning_rate", sa.Float(), nullable=False, server_default="0.0001"),
        sa.Column("storage_path", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("weights_sha256", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("is_best", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["experiment_id"], ["lab_experiments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )

    # 6. lab_evaluations
    op.create_table(
        "lab_evaluations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("experiment_id", sa.String(length=36), nullable=False),
        sa.Column("checkpoint_id", sa.String(length=36), nullable=True),
        sa.Column("benchmark_name", sa.String(length=100), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("sample_generations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["checkpoint_id"], ["lab_checkpoints.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["experiment_id"], ["lab_experiments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )


def downgrade() -> None:
    op.drop_table("lab_evaluations")
    op.drop_table("lab_checkpoints")
    op.drop_table("lab_experiments")
    op.drop_table("lab_tokenizers")
    op.drop_table("lab_datasets")
    op.drop_table("lab_models")
