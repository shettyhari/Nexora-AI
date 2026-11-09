"""
Isolated Training Job Orchestrator & Process Lifecycle Manager.
Manages job creation, validation, GPU availability checks, priority scheduling,
isolated subprocess execution, pause, resume, cancel, failure recovery, and log streaming.
NEVER runs training loops inside web request handlers.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lab.checkpoints.manager import CheckpointManager
from app.lab.runtime_bridge import resolve_worker_python
from app.lab.telemetry.monitor import HardwareTelemetryMonitor
from app.lab.training.frameworks import DistributedConfigGenerator
from app.lab.training.license_guard import LicenseGuard
from app.models.lab import (
    LabCheckpoint,
    LabDataset,
    LabExperiment,
    LabModel,
    LabTrainingJob,
)


def _is_pid_running(pid: Optional[int]) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        import psutil
        if not psutil.pid_exists(pid):
            return False
        proc = psutil.Process(pid)
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except Exception:
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False


class TrainingJobManager:
    """Orchestrates isolated training worker subprocesses with persistent DB + disk state."""

    JOBS_ROOT = "./lab_jobs"

    @classmethod
    def _ensure_job_dir(cls, job_id: str) -> str:
        job_dir = os.path.abspath(os.path.join(cls.JOBS_ROOT, job_id))
        os.makedirs(job_dir, exist_ok=True)
        return job_dir

    @classmethod
    async def create_job(
        cls,
        db: AsyncSession,
        name: str,
        base_model_id: str,
        dataset_id: Optional[str],
        training_method: str = "sft",
        framework: str = "trl",
        intended_use: str = "research",
        hyperparameters: Optional[Dict[str, Any]] = None,
        lora_config: Optional[Dict[str, Any]] = None,
        framework_config: Optional[Dict[str, Any]] = None,
        gpu_required: bool = False,
        priority: int = 1,
    ) -> LabTrainingJob:
        """Creates and validates a training job configuration & license compatibility."""
        # Resolve base model metadata
        model_name = base_model_id
        model_license = "Apache-2.0"
        arch_config: Dict[str, Any] = {
            "d_model": 64,
            "n_layers": 2,
            "n_heads": 4,
            "n_kv_heads": 2,
            "vocab_size": 256,
        }
        m_res = await db.execute(select(LabModel).where(LabModel.id == base_model_id))
        model_row = m_res.scalar_one_or_none()
        if model_row:
            model_name = f"{model_row.name} ({model_row.version})"
            model_license = model_row.license
            arch_config = dict(model_row.architecture_config or arch_config)

        # Resolve dataset metadata
        dataset_name = "Default Instruction & Alignment Research Corpus"
        dataset_license = "Apache-2.0"
        dataset_path: Optional[str] = None
        if dataset_id:
            d_res = await db.execute(select(LabDataset).where(LabDataset.id == dataset_id))
            ds_row = d_res.scalar_one_or_none()
            if not ds_row:
                raise ValueError(f"Dataset '{dataset_id}' not found in Model Lab.")
            dataset_name = f"{ds_row.name} (v{ds_row.version})"
            dataset_license = ds_row.license
            dataset_path = os.path.abspath(ds_row.storage_path) if ds_row.storage_path else None

        # Verify License Compatibility
        license_report = LicenseGuard.verify_compatibility(
            base_model_license=model_license,
            dataset_license=dataset_license,
            intended_use=intended_use,
            training_method=training_method,
        )
        if not license_report["approved"]:
            raise ValueError("; ".join(license_report["errors"]))

        # Check hardware availability
        hw = HardwareTelemetryMonitor.get_system_telemetry()
        if gpu_required and not hw["gpu_available"]:
            raise ValueError(
                "GPU is explicitly required for this job configuration, but no CUDA/MPS GPU is available on the host."
            )

        hp = {
            "learning_rate": 5e-4,
            "max_steps": 8,
            "batch_size": 2,
            "grad_accum_steps": 1,
            "max_seq_len": 48,
            "warmup_steps": 2,
            "weight_decay": 0.01,
            "beta": 0.1,
            "num_generations": 2,
            "seed": 42,
            **(hyperparameters or {}),
        }
        if int(hp["max_steps"]) < 1 or float(hp["learning_rate"]) <= 0:
            raise ValueError("Invalid hyperparameters: max_steps must be >= 1 and learning_rate > 0.")

        l_cfg = lora_config or {}
        if training_method in ("lora", "qlora") and not l_cfg:
            l_cfg = DistributedConfigGenerator.build_peft_lora_config(
                r=4,
                lora_alpha=8,
                quantization_bits=4 if training_method == "qlora" else None,
            )

        fw_cfg = {
            "architecture_config": arch_config,
            "dataset_path": dataset_path,
            "accelerate": DistributedConfigGenerator.build_accelerate_config(
                grad_accum_steps=int(hp["grad_accum_steps"])
            ),
            "deepspeed": DistributedConfigGenerator.build_deepspeed_config(
                zero_stage=2,
                micro_batch_size=int(hp["batch_size"]),
                grad_accum_steps=int(hp["grad_accum_steps"]),
            )
            if framework == "deepspeed"
            else None,
            "nemo": DistributedConfigGenerator.build_nemo_config(
                model_name=model_name,
                training_method=training_method,
                max_steps=int(hp["max_steps"]),
                lr=float(hp["learning_rate"]),
            )
            if framework == "nemo"
            else None,
            **(framework_config or {}),
        }

        # Create associated experiment record for unified lineage
        exp = LabExperiment(
            name=f"[{training_method.upper()}] {name}",
            description=f"Fine-tuning job using {framework} ({training_method}) on {dataset_name}",
            model_id=model_row.id if model_row else None,
            model_name=model_name,
            dataset_id=dataset_id,
            dataset_version="1.0.0",
            hyperparameters=hp,
            reproducibility_env=hw,
            status="created",
            max_steps=int(hp["max_steps"]),
            tags=["prompt5", training_method, framework],
        )
        db.add(exp)
        await db.flush()

        job_id = str(exp.id)  # keep traceable alignment or clean uuid
        import uuid
        job_id = str(uuid.uuid4())
        job_dir = cls._ensure_job_dir(job_id)

        job = LabTrainingJob(
            id=job_id,
            name=name,
            experiment_id=exp.id,
            base_model_id=base_model_id,
            base_model_name=model_name,
            base_model_license=model_license,
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            dataset_license=dataset_license,
            intended_use=intended_use,
            training_method=training_method,
            framework=framework,
            framework_config=fw_cfg,
            lora_config=l_cfg,
            hyperparameters=hp,
            license_verified=license_report["approved"],
            license_report=license_report,
            status="queued",
            priority=priority,
            device_type=hw["accelerator"],
            gpu_required=gpu_required,
            total_steps=int(hp["max_steps"]),
            hardware_snapshot=hw,
            checkpoint_dir=os.path.join(job_dir, "checkpoints"),
            log_file_path=os.path.join(job_dir, "training.log"),
            metrics_file_path=os.path.join(job_dir, "metrics.jsonl"),
            state_file_path=os.path.join(job_dir, "status.json"),
        )
        db.add(job)

        # Write job_spec.json to disk for isolated worker
        spec = {
            "job_id": job.id,
            "name": job.name,
            "experiment_id": exp.id,
            "training_method": job.training_method,
            "framework": job.framework,
            "hyperparameters": job.hyperparameters,
            "lora_config": job.lora_config,
            "architecture_config": arch_config,
            "dataset_path": dataset_path,
        }
        with open(os.path.join(job_dir, "job_spec.json"), "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2)

        await db.commit()
        await db.refresh(job)
        return job

    @classmethod
    async def start_job(cls, db: AsyncSession, job: LabTrainingJob, resume: bool = False) -> LabTrainingJob:
        """Spawns an isolated training worker subprocess via subprocess.Popen."""
        job_dir = cls._ensure_job_dir(job.id)
        spec_path = os.path.join(job_dir, "job_spec.json")
        if not os.path.exists(spec_path):
            raise ValueError(f"Job specification file missing at {spec_path}")

        with open(spec_path, "r", encoding="utf-8") as f:
            spec = json.load(f)

        if resume:
            # Find latest saved checkpoint directory on disk or DB
            resume_dir = None
            status_path = os.path.join(job_dir, "status.json")
            if os.path.exists(status_path):
                try:
                    with open(status_path, "r", encoding="utf-8") as sf:
                        st = json.load(sf)
                    resume_dir = st.get("output_checkpoint_path")
                except Exception:
                    pass
            if not resume_dir and job.output_checkpoint_id:
                c_res = await db.execute(select(LabCheckpoint).where(LabCheckpoint.id == job.output_checkpoint_id))
                c_row = c_res.scalar_one_or_none()
                if c_row:
                    resume_dir = c_row.storage_path
            if resume_dir and os.path.exists(resume_dir):
                spec["resume_from_checkpoint_dir"] = resume_dir
                with open(spec_path, "w", encoding="utf-8") as f:
                    json.dump(spec, f, indent=2)
        else:
            spec.pop("resume_from_checkpoint_dir", None)
            with open(spec_path, "w", encoding="utf-8") as f:
                json.dump(spec, f, indent=2)

        # Clear any old pause/cancel flags
        control_path = os.path.join(job_dir, "control.json")
        with open(control_path, "w", encoding="utf-8") as cf:
            json.dump({"action": "run"}, cf)

        backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        env = os.environ.copy()
        env["NEXORA_IN_ML_WORKER"] = "1"
        env["PYTHONPATH"] = backend_root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        worker_python = resolve_worker_python()

        log_fp = open(job.log_file_path, "a", encoding="utf-8")
        try:
            proc = subprocess.Popen(
                [worker_python, "-m", "app.lab.training.worker", "--job-dir", job_dir],
                cwd=backend_root,
                env=env,
                stdout=log_fp,
                stderr=subprocess.STDOUT,
            )
        finally:
            log_fp.close()

        job.status = "running"
        job.worker_pid = proc.pid
        job.error_message = None
        if not job.started_at:
            job.started_at = datetime.now(timezone.utc)

        if job.experiment_id:
            exp_res = await db.execute(select(LabExperiment).where(LabExperiment.id == job.experiment_id))
            exp = exp_res.scalar_one_or_none()
            if exp:
                exp.status = "running"

        await db.commit()
        await db.refresh(job)
        return job

    @classmethod
    async def sync_job_state(cls, db: AsyncSession, job: LabTrainingJob) -> LabTrainingJob:
        """
        Synchronizes isolated worker status.json + checkpoint artifacts into DB cleanly.
        Enforces strict checkpoint validation before marking completed.
        """
        if not job.state_file_path:
            return job

        dirty = False
        if os.path.exists(job.state_file_path):
            try:
                with open(job.state_file_path, "r", encoding="utf-8") as f:
                    st = json.load(f)

                job.current_step = int(st.get("current_step", job.current_step))
                job.total_steps = int(st.get("total_steps", job.total_steps))
                job.tokens_processed = int(st.get("tokens_processed", job.tokens_processed))
                job.tokens_per_sec = float(st.get("tokens_per_sec", job.tokens_per_sec))
                job.current_train_loss = st.get("current_train_loss", job.current_train_loss)
                job.current_val_loss = st.get("current_val_loss", job.current_val_loss)
                job.current_lr = st.get("current_lr", job.current_lr)
                job.device_type = st.get("device_type", job.device_type)
                job.loss_history = st.get("loss_history", job.loss_history)
                job.worker_pid = st.get("worker_pid", job.worker_pid)
                job.error_message = st.get("error_message")

                worker_status = st.get("status", job.status)

                # Sync checkpoints saved by isolated worker into LabCheckpoint table
                disk_ckpts = st.get("checkpoints", [])
                if disk_ckpts:
                    existing_res = await db.execute(
                        select(LabCheckpoint).where(LabCheckpoint.training_job_id == job.id)
                    )
                    existing_steps = {c.step: c for c in existing_res.scalars().all()}

                    latest_ckpt_id = job.output_checkpoint_id
                    for dc in disk_ckpts:
                        step_num = int(dc["step"])
                        if step_num not in existing_steps:
                            is_valid = bool(
                                dc["storage_path"] == st.get("output_checkpoint_path")
                                and st.get("checkpoint_validated", False)
                            )
                            new_ckpt = LabCheckpoint(
                                experiment_id=job.experiment_id,
                                training_job_id=job.id,
                                step=step_num,
                                epoch=int(dc.get("epoch", 1)),
                                version=f"1.0.step{step_num}",
                                format=dc.get("format", "huggingface_safetensors"),
                                train_loss=float(dc["train_loss"]),
                                val_loss=float(dc["val_loss"]),
                                perplexity=float(dc["perplexity"]),
                                learning_rate=float(dc["learning_rate"]),
                                storage_path=dc["storage_path"],
                                weights_sha256=dc["weights_sha256"],
                                is_best=bool(dc.get("is_best", False)),
                                is_adapter_only=bool(dc.get("is_adapter_only", False)),
                                adapter_config=job.lora_config if dc.get("is_adapter_only") else {},
                                validated=is_valid,
                                validation_report=st.get("validation_report", {}) if is_valid else {},
                            )
                            db.add(new_ckpt)
                            await db.flush()
                            latest_ckpt_id = new_ckpt.id
                        else:
                            ckpt_row = existing_steps[step_num]
                            if (
                                st.get("checkpoint_validated")
                                and ckpt_row.storage_path == st.get("output_checkpoint_path")
                                and not ckpt_row.validated
                            ):
                                ckpt_row.validated = True
                                ckpt_row.validation_report = st.get("validation_report", {})
                            latest_ckpt_id = ckpt_row.id

                    job.output_checkpoint_id = latest_ckpt_id

                # Strict completion validation
                if worker_status == "completed":
                    if st.get("checkpoint_validated") and job.output_checkpoint_id:
                        job.status = "completed"
                        job.checkpoint_validated = True
                        if not job.completed_at:
                            job.completed_at = datetime.now(timezone.utc)
                    else:
                        job.status = "failed"
                        job.checkpoint_validated = False
                        job.error_message = "Worker reported completion without validated checkpoint artifact."
                elif worker_status == "running" and not _is_pid_running(job.worker_pid):
                    # Worker died unexpectedly without reporting completion
                    job.status = "failed"
                    job.error_message = f"Isolated worker PID={job.worker_pid} terminated unexpectedly before completion."
                else:
                    job.status = worker_status
                    job.checkpoint_validated = bool(st.get("checkpoint_validated", False))

                dirty = True
            except Exception as exc:
                job.error_message = f"State sync error: {exc}"
                dirty = True
        elif job.status == "running" and not _is_pid_running(job.worker_pid):
            job.status = "failed"
            job.error_message = "Worker failed before initializing state file."
            dirty = True

        # Propagate summary to linked LabExperiment
        if dirty and job.experiment_id:
            exp_res = await db.execute(select(LabExperiment).where(LabExperiment.id == job.experiment_id))
            exp = exp_res.scalar_one_or_none()
            if exp:
                exp.status = "completed" if job.status == "completed" else ("aborted" if job.status == "cancelled" else job.status)
                exp.current_step = job.current_step
                exp.loss_history = job.loss_history
                if job.current_val_loss is not None:
                    exp.best_val_loss = job.current_val_loss
                    import math
                    exp.best_perplexity = round(math.exp(min(job.current_val_loss, 20.0)), 4)

        if dirty:
            await db.commit()
            await db.refresh(job)
        return job

    @classmethod
    async def pause_job(cls, db: AsyncSession, job: LabTrainingJob) -> LabTrainingJob:
        job_dir = cls._ensure_job_dir(job.id)
        control_path = os.path.join(job_dir, "control.json")
        with open(control_path, "w", encoding="utf-8") as cf:
            json.dump({"action": "pause"}, cf)
        if job.status in ("queued", "scheduled"):
            job.status = "paused"
            await db.commit()
            await db.refresh(job)
        return job

    @classmethod
    async def cancel_job(cls, db: AsyncSession, job: LabTrainingJob) -> LabTrainingJob:
        job_dir = cls._ensure_job_dir(job.id)
        control_path = os.path.join(job_dir, "control.json")
        with open(control_path, "w", encoding="utf-8") as cf:
            json.dump({"action": "cancel"}, cf)

        if job.status in ("queued", "scheduled", "paused"):
            job.status = "cancelled"
            await db.commit()
            await db.refresh(job)
        return job

    @classmethod
    async def recover_job(cls, db: AsyncSession, job: LabTrainingJob) -> LabTrainingJob:
        """Recovers a failed or paused job from its latest valid checkpoint on disk."""
        job.recovery_attempts = (job.recovery_attempts or 0) + 1
        return await cls.start_job(db, job, resume=True)

    @classmethod
    def read_logs(cls, job: LabTrainingJob, tail_lines: int = 200) -> str:
        if not job.log_file_path or not os.path.exists(job.log_file_path):
            return ""
        with open(job.log_file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-tail_lines:])
