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
    experiment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("lab_experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    epoch: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    train_loss: Mapped[float] = mapped_column(Float, nullable=False)
    val_loss: Mapped[float] = mapped_column(Float, nullable=False)
    perplexity: Mapped[float] = mapped_column(Float, nullable=False)
    learning_rate: Mapped[float] = mapped_column(Float, default=1e-4, nullable=False)

    storage_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    weights_sha256: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    is_best: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    experiment: Mapped["LabExperiment"] = relationship(
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
