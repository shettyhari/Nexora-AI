import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class LabModel(Base):
    """Proprietary Foundation Model Registry Entity."""
    __tablename__ = "lab_models"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="0.1.0", nullable=False)
    model_family: Mapped[str] = mapped_column(String(50), default="nano", nullable=False)  # nano, core, pro, custom
    architecture_type: Mapped[str] = mapped_column(String(50), default="decoder-only", nullable=False)
    parameter_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    base_model: Mapped[str] = mapped_column(String(100), default="scratch", nullable=False)
    license: Mapped[str] = mapped_column(String(100), default="Proprietary-Research", nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Architectural Hyperparameters
    architecture_config: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    # Default Training Hyperparameters
    training_config: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    # Evaluation Scores
    evaluation_results: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    # Linked Datasets
    dataset_associations: Mapped[List[str]] = mapped_column(JSONType, default=list, nullable=False)

    deployment_status: Mapped[str] = mapped_column(
        String(50),
        default="draft",
        nullable=False
    )  # draft, training, evaluating, registered, deployed, archived

    checkpoint_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    experiments: Mapped[List["LabExperiment"]] = relationship(
        "LabExperiment",
        back_populates="model",
        cascade="all, delete-orphan"
    )


class LabDataset(Base):
    """Dataset Management Entity with Provenance and Quality Tracking."""
    __tablename__ = "lab_datasets"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0", nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_uri: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="upload", nullable=False)  # upload, curated, synthetic, scraped
    license: Mapped[str] = mapped_column(String(100), default="Apache-2.0", nullable=False)
    file_format: Mapped[str] = mapped_column(String(50), default="jsonl", nullable=False)  # jsonl, txt, csv, parquet

    raw_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    cleaned_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    num_samples_raw: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    num_samples_cleaned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Train / Validation / Test counts
    train_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    val_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    test_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    language_distribution: Mapped[Dict[str, float]] = mapped_column(JSONType, default=dict, nullable=False)
    pii_findings: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    cleaning_stats: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    provenance: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)

    status: Mapped[str] = mapped_column(String(50), default="ready", nullable=False)  # uploaded, cleaning, ready, error
    storage_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    experiments: Mapped[List["LabExperiment"]] = relationship(
        "LabExperiment",
        back_populates="dataset"
    )


class LabTokenizer(Base):
    """Tokenizer Research Entity."""
    __tablename__ = "lab_tokenizers"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0", nullable=False)
    algorithm: Mapped[str] = mapped_column(String(50), default="bpe", nullable=False)  # bpe, unigram_sentencepiece
    vocab_size: Mapped[int] = mapped_column(Integer, default=32000, nullable=False)
    special_tokens: Mapped[List[str]] = mapped_column(JSONType, default=list, nullable=False)

    training_corpus_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("lab_datasets.id", ondelete="SET NULL"),
        nullable=True
    )
    vocab_data: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    evaluation_metrics: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="ready", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


class LabExperiment(Base):
    """Model Training and Fine-Tuning Experiment Tracking Entity."""
    __tablename__ = "lab_experiments"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    model_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("lab_models.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)

    dataset_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("lab_datasets.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    dataset_version: Mapped[str] = mapped_column(String(20), default="1.0.0", nullable=False)
    tokenizer_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    hyperparameters: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    reproducibility_env: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)

    status: Mapped[str] = mapped_column(
        String(50),
        default="created",
        nullable=False
    )  # created, running, completed, failed, aborted

    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_steps: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    best_val_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    best_perplexity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    loss_history: Mapped[List[Dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[List[str]] = mapped_column(JSONType, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    model: Mapped[Optional["LabModel"]] = relationship(
        "LabModel",
        back_populates="experiments"
    )
    dataset: Mapped[Optional["LabDataset"]] = relationship(
        "LabDataset",
        back_populates="experiments"
    )
    checkpoints: Mapped[List["LabCheckpoint"]] = relationship(
        "LabCheckpoint",
        back_populates="experiment",
        cascade="all, delete-orphan"
    )
    evaluations: Mapped[List["LabEvaluation"]] = relationship(
        "LabEvaluation",
        back_populates="experiment",
        cascade="all, delete-orphan"
    )


class LabCheckpoint(Base):
    """Model Weight and State Checkpoint Entity."""
    __tablename__ = "lab_checkpoints"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    experiment_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("lab_experiments.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    training_job_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True
    )
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    epoch: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    version: Mapped[str] = mapped_column(String(30), default="1.0.0", nullable=False)
    format: Mapped[str] = mapped_column(String(50), default="pytorch", nullable=False)

    train_loss: Mapped[float] = mapped_column(Float, nullable=False)
    val_loss: Mapped[float] = mapped_column(Float, nullable=False)
    perplexity: Mapped[float] = mapped_column(Float, nullable=False)
    learning_rate: Mapped[float] = mapped_column(Float, default=1e-4, nullable=False)

    storage_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    weights_sha256: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    is_best: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_adapter_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    adapter_config: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    validated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    validation_report: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    export_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    parent_checkpoint_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    is_active_rollback_target: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    experiment: Mapped[Optional["LabExperiment"]] = relationship(
        "LabExperiment",
        back_populates="checkpoints"
    )


class LabEvaluation(Base):
    """Model Evaluation and Benchmark Record Entity."""
    __tablename__ = "lab_evaluations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    experiment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("lab_experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    checkpoint_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("lab_checkpoints.id", ondelete="SET NULL"),
        nullable=True
    )
    benchmark_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metrics: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    sample_generations: Mapped[List[Dict[str, str]]] = mapped_column(JSONType, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    experiment: Mapped["LabExperiment"] = relationship(
        "LabExperiment",
        back_populates="evaluations"
    )


class LabTrainingJob(Base):
    """Isolated Distributed Training & Fine-Tuning Job Entity (SFT, LoRA, QLoRA, DPO, GRPO)."""
    __tablename__ = "lab_training_jobs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    experiment_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("lab_experiments.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    base_model_id: Mapped[str] = mapped_column(String(150), nullable=False)
    base_model_name: Mapped[str] = mapped_column(String(150), nullable=False)
    base_model_license: Mapped[str] = mapped_column(String(100), default="Apache-2.0", nullable=False)

    dataset_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("lab_datasets.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    dataset_name: Mapped[str] = mapped_column(String(150), default="Default Corpus", nullable=False)
    dataset_license: Mapped[str] = mapped_column(String(100), default="Apache-2.0", nullable=False)
    intended_use: Mapped[str] = mapped_column(String(50), default="research", nullable=False)  # research, internal, commercial

    training_method: Mapped[str] = mapped_column(String(50), default="sft", nullable=False)  # sft, instruction, lora, qlora, dpo, grpo, pretrain
    framework: Mapped[str] = mapped_column(String(50), default="trl", nullable=False)  # trl, transformers, peft, accelerate, deepspeed, nemo, pytorch
    framework_config: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    lora_config: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    hyperparameters: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)

    license_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    license_report: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)

    status: Mapped[str] = mapped_column(
        String(50),
        default="queued",
        nullable=False,
        index=True
    )  # queued, scheduled, running, paused, completed, failed, cancelled
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    worker_pid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    device_type: Mapped[str] = mapped_column(String(50), default="cpu", nullable=False)
    gpu_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_steps: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    tokens_processed: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    tokens_per_sec: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_train_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_val_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_lr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    loss_history: Mapped[List[Dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)
    hardware_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)

    checkpoint_dir: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    log_file_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    metrics_file_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    state_file_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)

    output_checkpoint_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    checkpoint_validated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recovery_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )


class LabBenchmarkSuite(Base):
    """Comprehensive 10-Dimension Model Evaluation, Comparison & Regression Entity."""
    __tablename__ = "lab_benchmark_suites"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0", nullable=False)

    candidate_model_name: Mapped[str] = mapped_column(String(150), nullable=False)
    candidate_checkpoint_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    baseline_model_name: Mapped[str] = mapped_column(String(150), nullable=False)
    baseline_checkpoint_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    dataset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    leakage_checked: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    leakage_overlap_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    leakage_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    leakage_report: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)

    dimension_scores: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    baseline_scores: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    deltas: Mapped[Dict[str, float]] = mapped_column(JSONType, default=dict, nullable=False)

    regression_passed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    regression_failures: Mapped[List[str]] = mapped_column(JSONType, default=list, nullable=False)
    human_ratings: Mapped[List[Dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)

    aggregate_candidate_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    aggregate_baseline_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


class LabOptimizationRun(Base):
    """Quantization, Memory & Inference Throughput Benchmark Entity."""
    __tablename__ = "lab_optimization_runs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    checkpoint_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    model_name: Mapped[str] = mapped_column(String(150), nullable=False)
    target_precision: Mapped[str] = mapped_column(String(30), default="int8_dynamic", nullable=False)

    batch_size: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    context_length: Mapped[int] = mapped_column(Integer, default=256, nullable=False)
    kv_cache_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    original_size_mb: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    optimized_size_mb: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    compression_ratio: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    ttft_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    tokens_per_sec: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    peak_memory_mb: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    context_scaling_results: Mapped[List[Dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)
    batch_scaling_results: Mapped[List[Dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)

    artifact_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


class LabInferenceDeployment(Base):
    """Independent OpenAI-Compatible Model Serving & Deployment Entity."""
    __tablename__ = "lab_inference_deployments"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    model_alias: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    checkpoint_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    model_name: Mapped[str] = mapped_column(String(150), nullable=False)

    engine: Mapped[str] = mapped_column(String(50), default="transformers", nullable=False)  # vllm, transformers, pytorch_native
    quantization: Mapped[str] = mapped_column(String(30), default="none", nullable=False)
    device: Mapped[str] = mapped_column(String(30), default="cpu", nullable=False)
    max_model_len: Mapped[int] = mapped_column(Integer, default=2048, nullable=False)
    max_concurrent_requests: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    gpu_memory_utilization: Mapped[float] = mapped_column(Float, default=0.85, nullable=False)

    status: Mapped[str] = mapped_column(String(30), default="healthy", nullable=False)
    requests_served: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    active_queue_depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_prompt_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_completion_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    last_health_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

