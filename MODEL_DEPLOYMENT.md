# NEXORA AI – Proprietary & External Model Deployment Architecture

**Version:** 2.0.0  

This document details how trained checkpoints in **NEXORA MODEL LAB** are verified, promoted into the live commercial catalog (`PublishedModel`), routed through `UnifiedModelGateway` with **strict zero-masquerading attribution**, and served via OpenAI-compatible `/v1/*` endpoints.

---

## 1. End-to-End Foundation Model Lifecycle

```text
[1. Data Pipeline & LicenseGuard]
     │ NFKC, PII Redact, SHA-256 Dedup, 80/10/10 Split, License Compatibility Check
     ▼
[2. Isolated Training Worker (TrainingJobManager)]
     │ Subprocess worker (.venv311 / worker-training, NEXORA_IN_ML_WORKER=1)
     │ Methods: SFT, Instruction, LoRA, QLoRA, DPO, GRPO -> Saves weights + SHA-256
     ▼
[3. 5-Point Checkpoint Validation (CheckpointManager.validate_checkpoint)]
     │ Exists & non-empty -> SHA-256 verified -> Weights load -> Zero NaN/Inf -> Forward pass
     ▼
[4. 10-Dimension Comparative Evaluation & Data Leakage Gate]
     │ 5-gram & SHA-256 overlap blocker vs baseline -> Regression check -> SafeTensors export
     ▼
[5. Commercial Catalog Bridge (PublishedModel -> ModelRegistry.sync_published_models)]
     │ Admin (/api/v1/admin/models/publish-checkpoint) or Lab (/api/v1/lab/checkpoints/{id}/publish)
     ▼
[6. Live Serving & Gateway Routing]
     ├─ Web Chat UI (/api/v1/messages SSE) + Model Selector (/api/v1/models)
     └─ OpenAI-Compatible API (/v1/models, /v1/chat/completions, /v1/completions, /v1/embeddings)
```

---

## 2. Pre-Training License & Validation Gates

1. **License Compliance Guard ([`LicenseGuard`](backend/app/lab/training/license_guard.py)):**
   - Before any job is created in `TrainingJobManager.create_job()`, `(base_model_license, dataset_license, intended_use, training_method)` is verified.
   - Non-commercial assets (`cc-by-nc-4.0`, `proprietary-research`, `nc-research-only`) are blocked when `intended_use="commercial"`.
   - Unknown/missing licenses are always rejected (`approved=False`).
2. **5-Point Checkpoint Validation ([`CheckpointManager`](backend/app/lab/checkpoints/manager.py)):**
   - Confirms artifact exists and `file_size_bytes > 0`.
   - Computes recursive/file SHA-256 and enforces match against `weights_sha256`.
   - Delegates tensor deserialization (via isolated worker `runtime_bridge.py` when web process lacks `torch`) across `model.safetensors`, `adapter_model.safetensors`, or `.pt` (`weights_only=True`).
   - Scans every parameter tensor for `NaN` and `Inf`.
   - Executes a forward-pass smoke test when model architecture config is attached.
   - Unvalidated checkpoints are strictly rejected (`400 Bad Request`) by both checkpoint deployment and production publishing routes.

---

## 3. Promoting Lab Models to Commercial Production

Approved researchers (`researcher`/`admin`) or platform administrators (`admin`) promote validated checkpoints without restarting the API server:

- **Researcher Bridge:** `POST /api/v1/lab/checkpoints/{checkpoint_id}/publish` (gated by `require_lab_access`)
- **Admin Bridge:** `POST /api/v1/admin/models/publish-checkpoint` (gated by `require_admin`, creates `AuditLog` entry `admin_checkpoint_published`)

Both routes:
1. Re-run `CheckpointManager.validate_checkpoint()` against disk weights + `weights_sha256`.
2. Upsert a [`PublishedModel`](backend/app/models/ecosystem.py) database record storing `id`, `display_name`, `provider`, `version`, `checkpoint_id`, `deployment_alias`, `min_plan_tier` (`free`, `pro`, `enterprise`), `input_price_per_million`, `output_price_per_million`, `is_enabled`, `is_proprietary=True`, and `approval_status="approved"`.
3. Immediately call `model_registry.sync_published_models([pub], checkpoint_paths=...)` so the model appears live in `/api/v1/models` and `/v1/models`.
4. `app.main.lifespan()` also executes this synchronization automatically at startup so published models survive restarts cleanly.

Administrators can toggle availability, adjust pricing, or raise `min_plan_tier` live via `PATCH /api/v1/admin/models/{model_id}`.

---

## 4. OpenAI-Compatible Serving (`backend/app/lab/inference/server.py`)

`InferenceDeploymentManager` exposes:
- `POST /api/v1/lab/deployments` — Loads a validated checkpoint into `transformers`, `vllm` (only when CUDA GPU & `vllm` exist; otherwise cleanly falls back to `transformers`), or `pytorch_native` (with optional `int8_dynamic` quantization), protected by per-alias `asyncio.Semaphore(max_concurrent_requests)`.
- `GET /v1/models` — Combines live `healthy` Lab deployments and active `ModelRegistry` models (`owned_by`, `proprietary`, `min_plan_tier`).
- `POST /v1/chat/completions` — Authenticates caller (`nex_live_` API key or JWT) via `authenticate_api_principal`, enforces plan RPM + token quota + `min_plan_tier`, routes to either the deployed Lab checkpoint runtime or `UnifiedModelGateway`, supports `stream=true` SSE (`chat.completion.chunk` + `[DONE]`), and persists `ApiUsageLog` + `BillingService.record_consumption()`.
- `POST /v1/completions` and `POST /v1/embeddings` — Full token accounting and commercial quota enforcement.

---

## 5. Truthful Attribution & Zero-Masquerading Guarantee

NEXORA strictly prohibits presenting an external or fallback model's output as a proprietary NEXORA model or silently claiming a fallback output came from a requested external frontier model (`UnifiedModelGateway` in [`backend/app/services/llm/gateway.py`](backend/app/services/llm/gateway.py)):

1. **Pre-Flight Provider Resolution (`resolve_execution_target`):**
   - Inspects `ModelDescriptor.provider` (unwrapping Python 3.12 `(str, Enum)` `.value` safely) and calls dynamic `provider.is_configured()`.
   - When an external model (e.g., `gpt-4o`) is requested while `OPENAI_API_KEY` is unconfigured, `resolve_execution_target()` explicitly switches target to `"nexora-flagship"` (`actual_provider="nexora"`, `fallback_used=True`, `fallback_from_model="gpt-4o"`).
2. **Runtime Failover Transparency:**
   - If an upstream external provider errors before emitting tokens during `stream()` or raises in `generate()`, the gateway seamlessly fails over to `nexora-flagship`, injects an explicit attribution notice in chat streams, and sets:
     - `resolved_model`: `"nexora-flagship"`
     - `actual_provider`: `"nexora"`
     - `fallback_used`: `true`
     - `fallback_from_model`: requested model ID
3. **Wire Visibility:**
   - **Web Chat SSE (`/api/v1/messages`):** Every `routing`, `token`, `reasoning`, and `done` event carries `resolved_model`, `actual_provider`, and `fallback_used` (`fallback_from_model` on `routing`/`done`), persisted to `Message` and `ApiUsageLog`.
   - **OpenAI API (`/v1/chat/completions`):** Response JSON sets top-level `"model": resp.model` (the actual executed model, not blindly echoing the requested string) plus `"nexora_attribution": { requested_model, resolved_model, actual_provider, fallback_used, fallback_from_model, cost_usd }`.
   - **Plan Gate Enforcement:** Requests to restricted models by Free tier users fail closed with `HTTP 403 Forbidden` rather than silently downgrading.

---

## 6. Safe Rollback Procedure

If a promoted model exhibits regressions:
1. Disable immediately in commercial traffic without losing checkpoint provenance:
   ```bash
   PATCH /api/v1/admin/models/{model_id}   # {"is_enabled": false}
   ```
2. Stop dedicated inference deployment (if mounted on `/v1`):
   ```bash
   POST /api/v1/lab/deployments/{deployment_id}/stop
   ```
3. Switch Lab rollback pointer to the last verified golden checkpoint:
   ```bash
   POST /api/v1/lab/checkpoints/{good_checkpoint_id}/rollback
   ```
   (`CheckpointManager.validate_checkpoint()` runs automatically before activating the rollback target.)
4. Republish the golden checkpoint ID via `POST /api/v1/admin/models/publish-checkpoint`.
