# NEXORA AI – Model Training, Fine-Tuning & GPU Infrastructure

This document details the **Prompt 5** engineering architecture extending **NEXORA MODEL LAB** with isolated fine-tuning workers, distributed training configuration synthesis, real hardware telemetry, strict checkpoint validation, 10-dimension benchmark comparisons, quantization benchmarking, and an independent OpenAI-compatible serving layer.

---

## 1. Architecture & Process Isolation

Training and inference workloads are strictly decoupled from FastAPI web request handlers:

```
┌─────────────────────────────────────────┐       ┌──────────────────────────────────────────────┐
│ FastAPI Control Plane (requirements.txt)│       │ Isolated ML Worker (requirements-training.txt)│
│                                         │       │                                              │
│ • /api/v1/lab/jobs (Create/Control)     │──────▶│ • python -m app.lab.training.worker          │
│ • LicenseGuard & Config Validation      │ spawn │   - LlamaForCausalLM / PEFT LoraConfig       │
│ • TrainingJobManager (subprocess.Popen) │       │   - SFT, Instruction, LoRA, QLoRA, DPO, GRPO │
│ • /api/v1/lab/telemetry (psutil / NVML) │       │   - Pause / Resume / Cancel Control Signals  │
│ • /v1/chat/completions (OpenAI Server)  │──────▶│ • app.lab.runtime_bridge (JSON Bridge)       │
└─────────────────────────────────────────┘       └──────────────────────────────────────────────┘
```

- **Vercel & Slim API Compatibility:** `backend/requirements.txt` remains lightweight for fast serverless/web startup, while GPU/training runtime packages are isolated in `backend/requirements-training.txt` (`torch`, `transformers`, `accelerate`, `peft`, `trl`, `datasets`, `safetensors`, `psutil`, `nvidia-ml-py`, plus Linux CUDA optional `bitsandbytes`, `deepspeed`, `vllm`).
- **Dual-Venv Bridge (`backend/app/lab/runtime_bridge.py`):** Automatically executes in-process when ML packages are installed in the active environment (standard Linux/Docker/GPU deployments) or cleanly dispatches ML operations to a dedicated worker virtual environment (`TRAINING_WORKER_PYTHON` / `.venv311` / `.venv-worker`) when separated.

---

## 2. Fine-Tuning Pipeline & Supported Methods

All fine-tuning runs execute real PyTorch + Hugging Face Transformers / PEFT gradient updates inside isolated child worker processes (`backend/app/lab/training/worker.py`):

| Method | Mechanism & Loss | Artifacts Produced |
| :--- | :--- | :--- |
| **`sft`** | Supervised autoregressive next-token cross-entropy (`LlamaForCausalLM`) | `model.safetensors`, `config.json`, `optimizer.pt`, `trainer_state.json` |
| **`instruction`** | Prompt-prefix token masking (`labels = -100` prior to `### Response:`) | Full SafeTensors HF directory |
| **`lora`** | Frozen base weights + trainable low-rank `q_proj`/`v_proj` PEFT adapters | `adapter_model.safetensors`, `adapter_config.json`, `base_weights.pt` |
| **`qlora`** | PEFT LoRA + 4-bit NF4 double-quantization configuration recipe | PEFT adapter bundle + quantization metadata |
| **`dpo`** | Reference policy log-ratio sigmoid optimization (`-logsigmoid(beta * delta)`) | Aligned HF SafeTensors directory |
| **`grpo`** | Group rollout sampling (`G` completions), verifiable reward normalization, KL penalty | Policy-aligned HF SafeTensors directory |

### License Compatibility Guard (`backend/app/lab/training/license_guard.py`)
Before scheduling any training job, `LicenseGuard.verify_compatibility()` validates `(base_model_license, dataset_license, intended_use)`:
- **Permissive Commercial (`Apache-2.0`, `MIT`, `BSD`, `CC-BY-4.0`, `Proprietary-Commercial`):** Approved for `research`, `internal`, and `commercial` fine-tuning.
- **Restricted (`Proprietary-Research`, `CC-BY-NC-4.0`):** Strictly **blocked (`HTTP 400`)** if `intended_use == "commercial"`.
- **Community / RAIL (`OpenRAIL-M`, `Llama-3.1-Community`):** Approved with explicit acceptable-use compliance obligations.

---

## 3. Training Job Lifecycle & Failure Recovery

Managed via `TrainingJobManager` (`backend/app/lab/training/job_manager.py`):
- **Scheduling & Validation:** Validates hyperparameters, licenses, and hardware (`gpu_required=True` raises `HTTP 400` on CPU hosts without silent downgrade).
- **Resumable Control Signals:** `control.json` coordinates `pause` and `cancel` cleanly at step boundaries without corrupting weights.
- **Crash Detection & Recovery:** Tracks `worker_pid` health via `psutil`; dead workers are flagged accurately (`failed`), and `POST /api/v1/lab/jobs/{id}/recover` resumes from the last verified checkpoint (`trainer_state.json` + `optimizer.pt`).
- **Strict Completion Gate:** A job is never marked `completed` unless `worker.py` exits cleanly **and** `CheckpointManager.validate_checkpoint()` passes all artifact checks.

---

## 4. Genuine Hardware & Training Telemetry

`HardwareTelemetryMonitor` (`backend/app/lab/telemetry/monitor.py`) probes:
1. **NVIDIA NVML (`pynvml` / `nvidia-smi`):** GPU count, name, driver, compute utilization %, VRAM used/free/total MB, core temperature (°C), power draw (W).
2. **PyTorch Accelerators (`torch.cuda` / `torch.backends.mps`):** CUDA version and compute capability.
3. **Host Compute (`psutil`):** Logical/physical CPU cores, real CPU utilization %, frequency MHz, RAM total/used/available GB, disk capacity.
4. **Zero Fabrication Policy:** When no GPU is installed, `gpu_available: false`, `accelerator: "cpu"`, and `gpu_status` honestly reports `"GPU Unavailable"`.

---

## 5. Checkpoint Validation, Export & Rollback

`CheckpointManager` (`backend/app/lab/checkpoints/manager.py`) provides:
1. **5-Point Validation Gate (`POST /api/v1/lab/checkpoints/{id}/validate`):**
   - File/directory existence and non-zero size check.
   - Cryptographic SHA-256 checksum match across all weight files.
   - Weight deserialization via `safetensors.torch.load_file` / `torch.load(..., weights_only=True)`.
   - Zero NaN / Inf tensor verification across every model parameter.
   - Live forward-pass sanity inference on `LlamaForCausalLM` / `PeftModel`.
2. **Release Export (`POST /api/v1/lab/checkpoints/{id}/export`):** Generates a clean SafeTensors bundle with `EXPORT_MANIFEST.json`.
3. **Validated Rollback (`POST /api/v1/lab/checkpoints/{id}/rollback`):** Rejects unvalidated targets and atomically shifts the active rollback pointer.

---

## 6. 10-Axis Comparative Benchmarks & Data Leakage Prevention

`BenchmarkEvaluator` (`backend/app/lab/evaluation/benchmark.py`):
- **10 Evaluation Dimensions:** `general_knowledge`, `reasoning`, `mathematics`, `coding`, `instruction_following`, `multilingual`, `long_context`, `factuality`, `safety`, `tool_calling`.
- **Leakage Guard:** Scans dataset JSONL/TXT rows using SHA-256 exact match and 5-gram normalized overlap against benchmark prompts, flagging/blocking leaked evaluations.
- **Regression Gate:** Compares candidate vs. baseline deltas (enforcing tighter `-2.0 pt` threshold on `safety`).
- **Human Evaluations:** Appends evaluator preferences (`candidate`/`tie`/`baseline`), coherence, usefulness, and safety ratings to versioned `LabBenchmarkSuite` records.

---

## 7. Quantization & Inference Performance Benchmarking

`ModelOptimizer` (`backend/app/lab/optimization/quantizer.py`):
- Supports `fp32`, `fp16`, `bf16`, `int8_dynamic` (via `torch.ao.quantization.quantize_dynamic` after merging any PEFT LoRA weights with `merge_and_unload()`), and `int4_nf4` storage sizing.
- Measures authentic **Time-To-First-Token (TTFT ms)**, **decode throughput (tokens/sec)** with KV-cache reuse, **`tracemalloc` peak memory (MB)**, **context-length prefill scaling** (`64, 128, 256, 512`), and **dynamic batch scaling** (`1, 2, 4`).

---

## 8. Independent OpenAI-Compatible Inference Server

Exposed natively at both `/v1/*` and `/api/v1/inference/v1/*`:
- `GET /v1/models`: Lists active healthy deployed checkpoints.
- `GET /v1/health`: Reports accelerator readiness, vLLM/Transformers/PyTorch capabilities, and aggregate requests served.
- `POST /v1/chat/completions`: Standard OpenAI request/response JSON and `stream=True` Server-Sent Events (`data: [DONE]`), protected by per-deployment asyncio concurrency semaphores and token accounting.
- `POST /v1/completions`: Standard prompt completion adapter.

