"""
NEXORA MODEL LAB – Prompt 5 Training, Fine-Tuning, Telemetry, Optimization,
Checkpoints & Comparative Benchmark REST API.
"""
import os
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.lab.checkpoints.manager import CheckpointManager
from app.lab.evaluation.benchmark import BenchmarkEvaluator
from app.lab.optimization.quantizer import ModelOptimizer
from app.lab.telemetry.monitor import HardwareTelemetryMonitor
from app.lab.training.frameworks import DistributedConfigGenerator, FrameworkInspector
from app.lab.training.job_manager import TrainingJobManager
from app.lab.training.license_guard import LicenseGuard
from app.models.lab import (
    LabBenchmarkSuite,
    LabCheckpoint,
    LabDataset,
    LabInferenceDeployment,
    LabModel,
    LabOptimizationRun,
    LabTrainingJob,
)

router = APIRouter(prefix="/lab", tags=["Model Lab Training & Infrastructure"])


# --- Request Schemas ---

class VerifyLicenseRequest(BaseModel):
    base_model_license: str
    dataset_license: str
    intended_use: str = "research"  # research, internal, commercial
    training_method: str = "lora"


class CreateTrainingJobRequest(BaseModel):
    name: str
    base_model_id: str
    dataset_id: Optional[str] = None
    training_method: str = "lora"  # sft, instruction, lora, qlora, dpo, grpo, pretrain
    framework: str = "trl"  # trl, transformers, peft, accelerate, deepspeed, nemo, pytorch
    intended_use: str = "research"
    gpu_required: bool = False
    priority: int = 1
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    lora_config: Optional[Dict[str, Any]] = None
    framework_config: Optional[Dict[str, Any]] = None
    auto_start: bool = False


class CompareBenchmarksRequest(BaseModel):
    name: str = "Base vs Fine-Tuned Suite"
    version: str = "1.0.0"
    candidate_model_name: str
    candidate_checkpoint_id: Optional[str] = None
    baseline_model_name: str = "Base Foundation Model"
    baseline_checkpoint_id: Optional[str] = None
    dataset_id: Optional[str] = None
    candidate_val_loss: Optional[float] = None
    baseline_val_loss: Optional[float] = None
    regression_tolerance: float = 5.0


class HumanRatingRequest(BaseModel):
    evaluator: str = "researcher"
    prompt: str
    preference: str = "candidate"  # candidate, baseline, tie
    coherence: int = Field(default=5, ge=1, le=5)
    helpfulness: int = Field(default=5, ge=1, le=5)
    safety_pass: bool = True
    notes: Optional[str] = None


class RunOptimizationRequest(BaseModel):
    checkpoint_id: Optional[str] = None
    model_name: str = "NEXORA NANO"
    target_precision: str = "int8_dynamic"  # fp32, fp16, bf16, int8_dynamic, int4_nf4
    batch_size: int = 1
    context_length: int = 128
    kv_cache_enabled: bool = True


class RollbackCheckpointRequest(BaseModel):
    target_model_id: Optional[str] = None
    reason: Optional[str] = None


# --- Hardware Telemetry & Framework Inspection ---

@router.get("/telemetry")
async def get_hardware_and_training_telemetry(db: AsyncSession = Depends(get_db)):
    """
    Returns genuine host CPU/RAM/GPU telemetry plus live active job metrics.
    Explicitly indicates when GPU hardware is unavailable.
    """
    hw = HardwareTelemetryMonitor.get_system_telemetry()

    res = await db.execute(select(LabTrainingJob).order_by(desc(LabTrainingJob.created_at)).limit(20))
    jobs = res.scalars().all()
    synced_jobs = []
    for j in jobs:
        if j.status in ("running", "paused"):
            j = await TrainingJobManager.sync_job_state(db, j)
        synced_jobs.append({
            "id": j.id,
            "name": j.name,
            "status": j.status,
            "training_method": j.training_method,
            "device_type": j.device_type,
            "current_step": j.current_step,
            "total_steps": j.total_steps,
            "tokens_per_sec": j.tokens_per_sec,
            "current_train_loss": j.current_train_loss,
            "current_val_loss": j.current_val_loss,
            "current_lr": j.current_lr,
        })

    return {
        "hardware": hw,
        "active_jobs": [j for j in synced_jobs if j["status"] in ("running", "queued", "scheduled")],
        "recent_jobs": synced_jobs[:8],
    }


@router.get("/frameworks")
async def get_training_frameworks():
    """Inspects installed versions & readiness of PyTorch, Transformers, Accelerate, PEFT, TRL, DeepSpeed, NeMo."""
    return FrameworkInspector.inspect_frameworks()


@router.post("/licenses/verify")
async def verify_license_compatibility(payload: VerifyLicenseRequest):
    """Checks whether base model and dataset licenses permit requested modification & deployment."""
    return LicenseGuard.verify_compatibility(
        base_model_license=payload.base_model_license,
        dataset_license=payload.dataset_license,
        intended_use=payload.intended_use,
        training_method=payload.training_method,
    )


@router.get("/distributed-configs/preview")
async def preview_distributed_configs(
    framework: str = Query("deepspeed"),
    training_method: str = Query("lora"),
    zero_stage: int = Query(2),
):
    """Generates validated Accelerate, PEFT, DeepSpeed, or NVIDIA NeMo training configs."""
    return {
        "framework": framework,
        "peft_lora": DistributedConfigGenerator.build_peft_lora_config(
            quantization_bits=4 if training_method == "qlora" else None
        ),
        "accelerate": DistributedConfigGenerator.build_accelerate_config(
            use_deepspeed=(framework == "deepspeed"), zero_stage=zero_stage
        ),
        "deepspeed": DistributedConfigGenerator.build_deepspeed_config(zero_stage=zero_stage),
        "nemo": DistributedConfigGenerator.build_nemo_config("NEXORA NANO", training_method=training_method),
    }


# --- Training Job Orchestration ---

@router.get("/jobs")
async def list_training_jobs(db: AsyncSession = Depends(get_db)):
    """Lists all isolated training & fine-tuning jobs, syncing live worker status."""
    res = await db.execute(select(LabTrainingJob).order_by(desc(LabTrainingJob.created_at)))
    jobs = res.scalars().all()
    out = []
    for j in jobs:
        if j.status in ("running", "paused"):
            j = await TrainingJobManager.sync_job_state(db, j)
        out.append(j)
    return out


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_training_job(payload: CreateTrainingJobRequest, db: AsyncSession = Depends(get_db)):
    """Creates a fine-tuning or pretraining job after validating license, config, and hardware."""
    try:
        job = await TrainingJobManager.create_job(
            db=db,
            name=payload.name,
            base_model_id=payload.base_model_id,
            dataset_id=payload.dataset_id,
            training_method=payload.training_method,
            framework=payload.framework,
            intended_use=payload.intended_use,
            hyperparameters=payload.hyperparameters,
            lora_config=payload.lora_config,
            framework_config=payload.framework_config,
            gpu_required=payload.gpu_required,
            priority=payload.priority,
        )
        if payload.auto_start:
            job = await TrainingJobManager.start_job(db, job, resume=False)
        return job
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Job creation failed: {str(exc)}")


@router.get("/jobs/{job_id}")
async def get_training_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Fetches a specific training job synchronized with its isolated worker state."""
    res = await db.execute(select(LabTrainingJob).where(LabTrainingJob.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")
    job = await TrainingJobManager.sync_job_state(db, job)
    return job


@router.post("/jobs/{job_id}/start")
async def start_training_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Schedules and spawns the isolated training worker subprocess."""
    res = await db.execute(select(LabTrainingJob).where(LabTrainingJob.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")
    if job.status == "running":
        raise HTTPException(status_code=400, detail="Training job is already running")
    return await TrainingJobManager.start_job(db, job, resume=False)


@router.post("/jobs/{job_id}/pause")
async def pause_training_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Signals the isolated training worker to save state and pause cleanly."""
    res = await db.execute(select(LabTrainingJob).where(LabTrainingJob.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")
    return await TrainingJobManager.pause_job(db, job)


@router.post("/jobs/{job_id}/resume")
async def resume_training_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Resumes a paused or failed job from its last checkpoint in a new worker process."""
    res = await db.execute(select(LabTrainingJob).where(LabTrainingJob.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")
    return await TrainingJobManager.start_job(db, job, resume=True)


@router.post("/jobs/{job_id}/recover")
async def recover_training_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Failure recovery: restarts failed worker from last verified checkpoint."""
    res = await db.execute(select(LabTrainingJob).where(LabTrainingJob.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")
    return await TrainingJobManager.recover_job(db, job)


@router.post("/jobs/{job_id}/cancel")
async def cancel_training_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Cancels a queued or active training job cleanly."""
    res = await db.execute(select(LabTrainingJob).where(LabTrainingJob.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")
    return await TrainingJobManager.cancel_job(db, job)


@router.get("/jobs/{job_id}/logs")
async def get_training_job_logs(job_id: str, tail: int = 200, db: AsyncSession = Depends(get_db)):
    """Reads live stdout/stderr training logs generated by the isolated worker."""
    res = await db.execute(select(LabTrainingJob).where(LabTrainingJob.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")
    job = await TrainingJobManager.sync_job_state(db, job)
    return {
        "job_id": job.id,
        "status": job.status,
        "logs": TrainingJobManager.read_logs(job, tail_lines=tail),
    }


# --- Checkpoint Validation, Export & Rollback ---

@router.post("/checkpoints/{checkpoint_id}/validate")
async def validate_checkpoint_artifact(checkpoint_id: str, db: AsyncSession = Depends(get_db)):
    """Verifies SHA-256 checksum, reloads weights, checks NaN/Inf, and tests forward pass."""
    res = await db.execute(select(LabCheckpoint).where(LabCheckpoint.id == checkpoint_id))
    ckpt = res.scalar_one_or_none()
    if not ckpt:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    report = CheckpointManager.validate_checkpoint(
        ckpt.storage_path,
        expected_sha256=ckpt.weights_sha256 or None,
    )
    ckpt.validated = bool(report["validated"])
    ckpt.validation_report = report
    await db.commit()
    await db.refresh(ckpt)
    return {"checkpoint": ckpt, "validation_report": report}


@router.post("/checkpoints/{checkpoint_id}/export")
async def export_checkpoint_bundle(
    checkpoint_id: str,
    target_format: str = Query("safetensors"),
    db: AsyncSession = Depends(get_db),
):
    """Exports a validated checkpoint into a portable Hugging Face / SafeTensors release bundle."""
    res = await db.execute(select(LabCheckpoint).where(LabCheckpoint.id == checkpoint_id))
    ckpt = res.scalar_one_or_none()
    if not ckpt:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    export_dir = os.path.abspath(os.path.join("./lab_exports", ckpt.id))
    try:
        exported = CheckpointManager.export_checkpoint(
            storage_path=ckpt.storage_path,
            export_dir=export_dir,
            target_format=target_format,
            metadata={"checkpoint_id": ckpt.id, "step": ckpt.step, "version": ckpt.version},
        )
        ckpt.export_path = exported["export_dir"]
        ckpt.validated = True
        await db.commit()
        await db.refresh(ckpt)
        return {"checkpoint": ckpt, "export": exported}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.post("/checkpoints/{checkpoint_id}/rollback")
async def rollback_to_checkpoint(
    checkpoint_id: str,
    payload: RollbackCheckpointRequest,
    db: AsyncSession = Depends(get_db),
):
    """Rolls back active deployment/model pointers to a previously validated checkpoint."""
    res = await db.execute(select(LabCheckpoint).where(LabCheckpoint.id == checkpoint_id))
    ckpt = res.scalar_one_or_none()
    if not ckpt:
        raise HTTPException(status_code=404, detail="Target rollback checkpoint not found")

    report = CheckpointManager.validate_checkpoint(ckpt.storage_path, expected_sha256=ckpt.weights_sha256 or None)
    if not report["validated"]:
        raise HTTPException(status_code=400, detail=f"Cannot rollback to unvalidated checkpoint: {report.get('error')}")

    # Reset previous rollback flags
    all_res = await db.execute(select(LabCheckpoint).where(LabCheckpoint.is_active_rollback_target == True))  # noqa: E712
    for prev in all_res.scalars().all():
        prev.is_active_rollback_target = False

    ckpt.is_active_rollback_target = True
    ckpt.validated = True

    if payload.target_model_id:
        m_res = await db.execute(select(LabModel).where(LabModel.id == payload.target_model_id))
        model = m_res.scalar_one_or_none()
        if model:
            model.version = f"{ckpt.version}-rollback"
            model.deployment_status = "registered"

    await db.commit()
    await db.refresh(ckpt)
    return {
        "status": "rolled_back",
        "active_checkpoint_id": ckpt.id,
        "version": ckpt.version,
        "reason": payload.reason or "Manual safety/regression rollback",
    }


# --- 10-Dimension Comparative Evaluation & Human Feedback ---

@router.get("/benchmarks")
async def list_benchmark_suites(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(LabBenchmarkSuite).order_by(desc(LabBenchmarkSuite.created_at)))
    return res.scalars().all()


@router.post("/benchmarks/compare", status_code=status.HTTP_201_CREATED)
async def run_comparative_benchmark(payload: CompareBenchmarksRequest, db: AsyncSession = Depends(get_db)):
    """
    Runs 10-dimension benchmark comparison between fine-tuned candidate and baseline,
    verifying training/eval data leakage prevention and regression thresholds.
    """
    cand_path = None
    cand_loss = payload.candidate_val_loss
    if payload.candidate_checkpoint_id:
        c_res = await db.execute(select(LabCheckpoint).where(LabCheckpoint.id == payload.candidate_checkpoint_id))
        c_row = c_res.scalar_one_or_none()
        if c_row:
            cand_path = c_row.storage_path
            if cand_loss is None:
                cand_loss = c_row.val_loss

    base_path = None
    base_loss = payload.baseline_val_loss
    if payload.baseline_checkpoint_id:
        b_res = await db.execute(select(LabCheckpoint).where(LabCheckpoint.id == payload.baseline_checkpoint_id))
        b_row = b_res.scalar_one_or_none()
        if b_row:
            base_path = b_row.storage_path
            if base_loss is None:
                base_loss = b_row.val_loss

    ds_path = None
    if payload.dataset_id:
        d_res = await db.execute(select(LabDataset).where(LabDataset.id == payload.dataset_id))
        d_row = d_res.scalar_one_or_none()
        if d_row:
            ds_path = d_row.storage_path

    comp = BenchmarkEvaluator.compare_models(
        candidate_model_name=payload.candidate_model_name,
        baseline_model_name=payload.baseline_model_name,
        candidate_checkpoint_path=cand_path,
        baseline_checkpoint_path=base_path,
        dataset_path=ds_path,
        candidate_val_loss=cand_loss,
        baseline_val_loss=base_loss,
        regression_tolerance=payload.regression_tolerance,
    )

    suite = LabBenchmarkSuite(
        id=str(uuid.uuid4()),
        name=payload.name,
        version=payload.version,
        candidate_model_name=payload.candidate_model_name,
        candidate_checkpoint_id=payload.candidate_checkpoint_id,
        baseline_model_name=payload.baseline_model_name,
        baseline_checkpoint_id=payload.baseline_checkpoint_id,
        dataset_id=payload.dataset_id,
        leakage_checked=comp["leakage_report"]["checked"],
        leakage_overlap_count=comp["leakage_report"]["overlap_count"],
        leakage_blocked=comp["leakage_report"]["leakage_blocked"],
        leakage_report=comp["leakage_report"],
        dimension_scores=comp["dimension_scores"],
        baseline_scores=comp["baseline_scores"],
        deltas=comp["deltas"],
        regression_passed=comp["regression_passed"],
        regression_failures=comp["regression_failures"],
        human_ratings=[],
        aggregate_candidate_score=comp["aggregate_candidate_score"],
        aggregate_baseline_score=comp["aggregate_baseline_score"],
    )
    db.add(suite)
    await db.commit()
    await db.refresh(suite)
    return suite


@router.post("/benchmarks/{suite_id}/human-rating")
async def add_human_evaluation_rating(
    suite_id: str,
    payload: HumanRatingRequest,
    db: AsyncSession = Depends(get_db),
):
    """Appends human preference & quality judgment to a versioned benchmark suite."""
    import time

    res = await db.execute(select(LabBenchmarkSuite).where(LabBenchmarkSuite.id == suite_id))
    suite = res.scalar_one_or_none()
    if not suite:
        raise HTTPException(status_code=404, detail="Benchmark suite not found")

    ratings = list(suite.human_ratings or [])
    ratings.append({
        "evaluator": payload.evaluator,
        "prompt": payload.prompt,
        "preference": payload.preference,
        "coherence": payload.coherence,
        "helpfulness": payload.helpfulness,
        "safety_pass": payload.safety_pass,
        "notes": payload.notes,
        "timestamp": time.time(),
    })
    suite.human_ratings = ratings
    await db.commit()
    await db.refresh(suite)
    return suite


# --- Model Optimization & Quantization Benchmarking ---

@router.get("/optimizations")
async def list_optimization_runs(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(LabOptimizationRun).order_by(desc(LabOptimizationRun.created_at)))
    return res.scalars().all()


@router.post("/optimizations/run", status_code=status.HTTP_201_CREATED)
async def run_model_optimization(payload: RunOptimizationRequest, db: AsyncSession = Depends(get_db)):
    """Executes real quantization & inference latency/memory/context/batch benchmarking."""
    ckpt_path = None
    if payload.checkpoint_id:
        c_res = await db.execute(select(LabCheckpoint).where(LabCheckpoint.id == payload.checkpoint_id))
        ckpt = c_res.scalar_one_or_none()
        if not ckpt:
            raise HTTPException(status_code=404, detail="Checkpoint not found")
        ckpt_path = ckpt.storage_path

    run_id = str(uuid.uuid4())
    out_dir = os.path.abspath(os.path.join("./lab_optimized", run_id))
    try:
        result = ModelOptimizer.run_optimization_and_benchmark(
            target_precision=payload.target_precision,
            checkpoint_path=ckpt_path,
            batch_size=payload.batch_size,
            context_length=payload.context_length,
            kv_cache_enabled=payload.kv_cache_enabled,
            out_dir=out_dir,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Optimization benchmark failed: {str(exc)}")

    run_rec = LabOptimizationRun(
        id=run_id,
        checkpoint_id=payload.checkpoint_id,
        model_name=payload.model_name,
        target_precision=result["target_precision"],
        batch_size=payload.batch_size,
        context_length=payload.context_length,
        kv_cache_enabled=payload.kv_cache_enabled,
        original_size_mb=result["original_size_mb"],
        optimized_size_mb=result["optimized_size_mb"],
        compression_ratio=result["compression_ratio"],
        ttft_ms=result["ttft_ms"],
        tokens_per_sec=result["tokens_per_sec"],
        peak_memory_mb=result["peak_memory_mb"],
        context_scaling_results=result["context_scaling_results"],
        batch_scaling_results=result["batch_scaling_results"],
        artifact_path=result["artifact_path"],
        status="completed",
    )
    db.add(run_rec)
    await db.commit()
    await db.refresh(run_rec)
    return run_rec

