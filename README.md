# NEXORA AI – Enterprise Autonomous AI Platform

NEXORA AI is a production-grade, full-stack ChatGPT-style neural application built with a **Next.js (React 18 / TypeScript / Tailwind CSS)** frontend, an asynchronous **FastAPI (Python 3.12)** backend, **SQLAlchemy 2.0** with **Alembic** migrations, **PostgreSQL / SQLite** with **pgvector**, and **Redis** caching.

---

## 🚀 Key Features

### 1. Unified Model Gateway & Provider Adapters
- **Multi-Provider Support**: Pluggable adapters for **Google Gemini** (1.5 Flash/Pro), **OpenAI** (GPT-4o, GPT-4o-mini), **Anthropic Claude** (3.5 Sonnet, 3.5 Haiku), **Hugging Face** (Llama 3.1 70B, DeepSeek-R1), **Self-Hosted Inference** (Ollama, vLLM, LM Studio), and **NEXORA Proprietary Flagship & Local Resilience Fallback**.
- **Common Gateway Protocol**: Unified `LLMRequest`, `LLMResponse`, and `LLMStreamChunk` abstraction across all providers.
- **Resilience & Graceful Failover**: Automatic cascaded failover to local fallback if an upstream cloud provider key is missing or rate-limited.
- **Provider Health Checks**: Live latency, status, and model discovery monitored concurrently via `/api/v1/gateway/health`.

### 2. Model Registry & Dynamic Selection
- **Centralized Registry**: Dynamic catalog specifying context window, maximum output tokens, supported modalities (text, vision), capabilities (streaming, reasoning, function calling, JSON schema), deployment, and pricing metadata.
- **Token Cost Tracking**: Real-time prompt and completion token cost accounting based on input/output per million pricing.
- **Dynamic Frontend Integration**: Populates the frontend Model Selector directly from the registry.

### 3. Intelligent Model Router
- **Autonomous Selection**: Automatically routes prompts to the optimal model based on detected user intent (coding, math/reasoning, fast Q&A, vision, large context), task complexity, token length, cost, and provider health.
- **Manual User Override**: Users can explicitly pick any specific model, honoring the choice with `is_override = true`.
- **Transparency Policy (No Silent Switching)**: Every response surfaces which model answered and why (`resolved_model` and `routing_reason`) directly in the UI.

### 4. 8-Stage Advanced Reasoning Framework
- **Orchestrated Workflow**:
  1. Classify Request & Profile Task
  2. Identify Capabilities (Vision, Code, Math)
  3. Determine Tool Needs (Web Search, Memory, RAG)
  4. Context Retrieval (Semantic Memory + Hybrid RAG + Web Search)
  5. Select Appropriate Model
  6. Assemble & Budget Context Window
  7. Stream Output with Reasoning Tokens
  8. Validate & Persist Metrics and Citations
- **Private Internal Reasoning**: Displays concise calculations, conclusions, and evidence with collapsible deep thought accordions.

### 5. Memory Engine (Semantic Vector Storage)
- **Multi-Tier Memory**: Short-term conversation memory, long-term user memory, project memory, and user preferences.
- **Semantic Vector Retrieval**: Vector embeddings with cosine similarity matching.
- **Duplicate Detection**: Computes semantic similarity prior to insertion; if similarity $\ge 0.88$, updates existing memory rather than duplicating.
- **User Control & Data Isolation**: Full user-controlled inspection, manual creation, and deletion with strict `user_id == current_user.id` isolation.

### 6. RAG Engine (Hybrid Search & RRF Reranking)
- **Document Ingestion**: Recursive character chunker with overlap across text, markdown, and code documents.
- **Hybrid Search**: Dense vector retrieval + sparse **BM25Okapi** lexical search.
- **Reciprocal Rank Fusion (RRF)**: Reranks combined dense and sparse candidates ($k=60$) for superior retrieval relevance.
- **Citation Generation**: Emits explicit citations `[Source 1: filename.md (Chunk 2)]` grounding AI responses.

### 7. Context Engine & Token Budgeting
- **Exact Token Counting**: Powered by `tiktoken` (o200k_base / cl100k_base) with heuristic fallback.
- **Window Budgeting**: Calculates model input budgets reserving output space ($Context - Output - 1000$).
- **Conversation Compression**: Condenses older messages into an executive summary block when context thresholds are reached while preserving recent dialogue intact.

### 8. Complete Chat Interface & Experience
- **NEXORA Brand Identity**: Futuristic neon-cyan and deep obsidian palette with original SVG logo and wordmark.
- **Full Conversation Management**: Create, rename, pin, archive, search (`⌘K`), and delete conversations.
- **Markdown & Math**: Full GitHub Flavored Markdown (GFM), syntax-highlighted code blocks with copy button, responsive tables, and inline/block LaTeX formulas via KaTeX.
- **Chat Composer**: Multiline auto-resizing textarea (`Enter` to send, `Shift + Enter` for new line), file uploads, model selector, reasoning toggle, web grounding toggle, and voice modal.
- **Light & Dark Mode**: Persistent theme toggle with zero-flicker initialization.

### 9. Multimodal AI & Agentic Intelligence (Prompt 3)
- **Image Intelligence**: Upload, OCR text extraction, screenshot inspection, chart and diagram interpretation, visual Q&A, and image generation.
- **Voice Intelligence**: Real microphone input, Speech-to-Text (`/voice/transcribe`), Text-to-Speech audio synthesis (`/voice/synthesize`), audio summarization, and interactive audio controls.
- **Video Intelligence**: Video upload, metadata extraction, scene segmentation with clickable timestamps `[MM:SS]`, video summarization, and background async media processing (`media_jobs`).
- **Document Intelligence**: Multi-format parser for **PDF, DOCX, XLSX, CSV, PPTX, TXT, JSON**, table extraction into Markdown, comparative analysis, and direct RAG ingestion.
- **Authorized Web Research Agent**: Search, safe page retrieval, prompt injection defense, and synthesized research reports with verified non-fabricated citations.
- **Multi-Agent Framework**: 8 autonomous specialized agents:
  1. `ORCHESTRATOR`: Coordinates plans and multi-agent workflows.
  2. `RESEARCH AGENT`: Conducts web/literature research and verifies sources.
  3. `CODING AGENT`: Writes, reviews, refactors, and tests code.
  4. `DATA ANALYSIS AGENT`: Processes tabular data and generates charts.
  5. `DOCUMENT AGENT`: Analyzes, parses, and compares files.
  6. `BROWSER AGENT`: Interacts with authorized external websites.
  7. `VISION AGENT`: Deciphers diagrams, charts, and images.
  8. `PERSONAL ASSISTANT AGENT`: General task coordination and productivity.
- **Standardized Tool Execution Engine & Sandbox**:
  - Permission levels: `READ`, `ANALYZE`, `PREPARE`, and `EXECUTE`.
  - Sensitive action approval gate before code execution.
  - Subprocess Python sandbox with static AST analyzer (`CodeASTAnalyzer`) blocking dangerous modules (`os`, `subprocess`, `socket`, `ctypes`, `eval`, `exec`).
  - Strict SSRF defense (`SSRFValidator`) blocking private subnets, cloud metadata, and loopback IPs.
- **Enhanced Multimodal UI**: Real Voice Mode modal with waveform visualizer, File Preview modal with video timestamp navigation and table views, and Multi-Agent Activity drawer.

### 10. Proprietary Foundation Model Research Lab (Prompt 4)
- **Isolated Research Environment**: Dedicated `/lab` route and backend research infrastructure isolated from user-facing chat services.
- **Model Registry & Roadmap**:
  - **NEXORA NANO** (~45M params): High-velocity experimentation for hyperparameter sensitivity and tokenizer testing.
  - **NEXORA CORE** (~1.2B params): General-purpose instruction and reasoning foundation model.
  - **NEXORA PRO** (~8.4B params): Flagship research target for multi-step reasoning, coding, and mathematical theorem proving.
- **Dataset Management & Quality Pipeline**:
  - Ingestion of JSONL, TXT, CSV with complete cryptographic provenance.
  - 7-stage pipeline: Unicode NFKC normalization, regex PII detection & redaction (emails, phones, SSNs, IPs, credit cards via Luhn's algorithm), exact SHA-256 deduplication, quality filtering, language identification, and deterministic 80/10/10 splitting.
- **Tokenizer Research Engine**:
  - Authentic Byte-Pair Encoding (BPE) iterative merge learner and SentencePiece unigram modeling.
  - Subword fertility, compression ratio (bytes per token), OOV rate, and cross-lingual compression benchmarking.
- **Decoder-Only Transformer Architecture**:
  - RoPE rotary position embeddings, RMSNorm root-mean-square normalization, Multi-Head & Grouped-Query Attention (GQA) with causal masking, SwiGLU feed-forward networks, and autoregressive cross-entropy loss.
  - Analytical parameter counter, FLOPs estimator, and memory footprint calculator.
- **Experiment Tracking & Reproducibility**:
  - MLflow-style tracking logging step-by-step training and validation loss curves, cosine learning rate schedules, and validation perplexity.
  - Verifiable checkpoints with SHA-256 weights digests.
  - Immutable reproducibility lock manifests enabling one-click twin run reproduction.
- **Model Lab UI**: Comprehensive admin workbench with Model Registry, Dataset Library, Tokenizer Lab, Architecture Workbench, Experiment Tracker, Checkpoint Browser, and Evaluation History.

### 11. Model Training, Fine-Tuning & GPU Infrastructure (Prompt 5)
- **Authentic Deep Learning Stack**: Integrated `PyTorch`, `Hugging Face Transformers`, `Accelerate`, `PEFT`, `TRL`, plus `DeepSpeed ZeRO-1/2/3` and `NVIDIA NeMo` config generators (`backend/requirements-training.txt`), while keeping `backend/requirements.txt` slim & Vercel-compatible.
- **Fine-Tuning Pipeline**: Real gradient updates across **SFT**, **Instruction Tuning** (prompt token masking), **LoRA**, **QLoRA** (4-bit NF4 config), **DPO** (reference-policy log-ratio loss), and **GRPO** (group rollouts with verifiable rewards & KL penalty), gated by **LicenseGuard** compatibility enforcement.
- **Isolated Training Job Manager**: Spawns isolated child training workers via `subprocess.Popen` (never in web request handlers) with priority scheduling, `pause`/`resume`/`cancel`/`recover`, live log tailing, and strict post-training checkpoint validation.
- **Genuine Hardware Telemetry**: Real CPU, RAM, Disk, and GPU telemetry (`pynvml`, `nvidia-smi`, `torch.cuda`, `torch.backends.mps`, `psutil`); honestly reports `"GPU Unavailable"` on CPU hosts without simulation.
- **Checkpoint Management**: Cryptographic SHA-256 digest verification, weight reload, NaN/Inf scan, forward-pass validation gate, SafeTensors release export (`EXPORT_MANIFEST.json`), and validated rollback.
- **10-Dimension Comparative Benchmarks & Optimization**: Evaluates base vs. fine-tuned models across 10 core capabilities with 5-gram/SHA-256 **data leakage prevention**, regression gates, human preference ratings, and PyTorch `int8_dynamic` / `bf16` / `fp16` / `int4_nf4` TTFT, throughput, memory, context & batch scaling benchmarks.
- **Independent OpenAI-Compatible Serving**: Dedicated `/v1/models`, `/v1/health`, `/v1/embeddings`, `/v1/chat/completions` (JSON + SSE `[DONE]`), and `/v1/completions` endpoints with concurrency semaphores and token accounting. See [`TRAINING_INFRASTRUCTURE.md`](TRAINING_INFRASTRUCTURE.md).

### 12. Production-Grade Independent Commercial AI Ecosystem (Prompt 6)
- **Proprietary & External Model Integration (`006_production_ecosystem`)**: Zero-downtime Lab-to-Production promotion (`PublishedModel`) via `/api/v1/lab/checkpoints/{id}/publish` & `/api/v1/admin/models/publish-checkpoint` backed by SHA-256 checkpoint verification and truthful zero-masquerading Gateway attribution (`resolved_model`, `actual_provider`, `fallback_used`, `fallback_from_model`).
- **Commercial Billing, Quotas & Entitlements (`/billing`)**: `free`, `pro`, and `enterprise` tiers (`SubscriptionPlan`), monthly/annual cycles, automatic period reset, paid invoices (`BillingInvoice`), Stripe HMAC-SHA256 webhook verification, sliding-window RPM rate limiting (`SlidingWindowRateLimiter` Redis/in-memory), upload caps (`413`), and monthly token quota gates.
- **Developer Platform & OpenAI API (`/developer` & `/v1/*`)**: Self-service cryptographic `nex_live_...` API keys stored solely as SHA-256 digests (`DeveloperApiKey`), instant revocation/rotation, and OpenAI SDK-compatible `/v1/models`, `/v1/embeddings`, `/v1/chat/completions`, and `/v1/completions` with real token & cost logging (`ApiUsageLog`).
- **Administration Control Center (`/admin`)**: Strictly `role == "admin"` RBAC console for managing users/roles/plans, enabling/disabling models and pricing, publishing verified checkpoints, checking provider credentials, inspecting `SecurityEvent` & `AuditLog` feeds, and monitoring infrastructure health.
- **Hardened Security & GDPR Erasure**: Path confinement (`resolve_safe_file_path`), SVG `nosniff`/`attachment` headers, AST Python sandbox, SSRF perimeter validator, HSTS/CSP-safe security middleware, startup `SECRET_KEY` validation (`validate_production_secrets`), and `DELETE /api/v1/users/me` GDPR data erasure.
- **Production Infrastructure, Object Storage & Disaster Recovery**: Segmented `docker-compose.prod.yml` (`nginx`, `frontend`, `backend`, `postgres`, `redis`, isolated `worker-training`, read-only `worker-inference`), `S3`/`R2`/`MinIO` + local confined storage (`ObjectStorageService`), Prometheus `GET /metrics`, `.github/workflows/ci.yml`, `backend/scripts/backup_db.py`, and `backend/scripts/benchmark_load.py`.

---

## 🛠 Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | Next.js 14 (App Router: `/`, `/billing`, `/developer`, `/lab`, `/admin`, `/profile`), React 18, TypeScript, Tailwind CSS, Lucide Icons, KaTeX, React Markdown |
| **Backend** | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 Async, Uvicorn, HTTPX, Boto3 (S3 optional) |
| **Database** | PostgreSQL 16 (Production) / SQLite Async (Local Dev), Alembic Migrations (`001`–`006`) |
| **Vector Engine** | pgvector (PostgreSQL) / Cosine Vector Generator (Local Dev) |
| **Hybrid Search** | BM25Okapi + Dense Vector Embeddings + Reciprocal Rank Fusion |
| **Cache & Limits**| Redis 7 (Distributed sliding-window rate limiter & cache with in-memory fallback) |
| **Edge & Ops** | Nginx 1.27 Reverse Proxy (SSE zero-buffer + rate limits), Docker Compose, GitHub Actions CI, Prometheus `/metrics` |
| **AI Providers** | Google Gemini, OpenAI, Anthropic Claude, Hugging Face, Self-Hosted (Ollama/vLLM), NEXORA Proprietary & Fine-Tuned Checkpoints |

---

## 📚 Documentation Index

| Document | Scope |
| :--- | :--- |
| [`API_DOCS.md`](API_DOCS.md) | Complete REST, SSE, OpenAI `/v1/*`, Billing, Developer, Lab, and Admin API reference |
| [`PRODUCTION_DEPLOYMENT.md`](PRODUCTION_DEPLOYMENT.md) | Production/Staging env templates, `SECRET_KEY` guards, Docker Compose & Vercel deploys |
| [`INFRASTRUCTURE.md`](INFRASTRUCTURE.md) | Multi-service topology, internal network isolation, Nginx proxy, S3 storage & CI/CD |
| [`DATABASE_BACKUP_STRATEGY.md`](DATABASE_BACKUP_STRATEGY.md) | `backup_db.py` (`pg_dump`/SQLite online backup), SHA-256 manifests, PITR & restore procedures |
| [`MODEL_DEPLOYMENT.md`](MODEL_DEPLOYMENT.md) | Model Lab validation, production promotion bridge, OpenAI serving & rollback |
| [`TRAINING_INFRASTRUCTURE.md`](TRAINING_INFRASTRUCTURE.md) | Prompt 5 SFT/LoRA/QLoRA/DPO/GRPO training workers & quantization benchmarks |
| [`SECURITY_AUDIT_REPORT.md`](SECURITY_AUDIT_REPORT.md) | Verified attack-surface controls, audit remediations & hardening checklist |
| [`PERFORMANCE_REPORT.md`](PERFORMANCE_REPORT.md) | Authentic measured HTTP load (`c=1,10,25`), SSE TTFT, RAG & CSV parse benchmarks |
| [`OPERATIONAL_RUNBOOKS.md`](OPERATIONAL_RUNBOOKS.md) | SRE playbooks for failover, worker recovery, key compromise, webhooks & DB restore |
| [`RELEASE_NOTES.md`](RELEASE_NOTES.md) | Complete `v2.0.0` commercial release notes & upgrade steps |

---

## ⚡ Quickstart

### Prerequisites
- Node.js 18+ and npm
- Python 3.12+ (or `uv`)
- Docker & Docker Compose (optional)

### 1. Environment Setup
```bash
cp .env.example .env
```
Add any API keys you wish to use (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.). If omitted, NEXORA seamlessly operates with the built-in diagnostic neural fallback.

### 2. Local Development

#### Start Backend:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Optional: install PyTorch / Transformers / PEFT / TRL worker stack for NEXORA MODEL LAB
# uv pip install -r requirements-training.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```
Backend API will be accessible at `http://localhost:8000` (Swagger docs at `/docs`).

#### Start Frontend:
```bash
cd frontend
npm install
npm run dev
```
Frontend will be accessible at `http://localhost:3000`.

### 3. Vercel Multi-Services Deployment

NEXORA AI is configured for one-click monorepo deployment on **Vercel** as a multi-service project:
- **`backend` service:** Asynchronous FastAPI Python service mounted in `backend/` (`framework: fastapi`, entrypoint `backend/main.py`).
- **`frontend` service:** Next.js 14 App Router service mounted in `frontend/` (`framework: nextjs`).
- **Service Binding:** Vercel automatically injects `process.env.BACKEND_URL` into the frontend service for secure internal communication.
- **Top-Level Rewrites:** `/api/(.*)` routes directly to `backend`, while `/(.*)` routes to `frontend`.

#### Local Testing with Vercel CLI:
```bash
vercel dev
```

#### Deploy to Vercel:
```bash
vercel
```

---

## 🧪 Automated Testing, Benchmarks & Disaster Recovery Drills

Run the complete **91-test** backend verification suite:
```bash
cd backend
pytest -v
```

Validate TypeScript + Next.js production build (`12` App Router routes):
```bash
cd frontend
npm run build
```

Run live concurrency/latency benchmarks and verified DB backup/restore drills:
```bash
cd backend
python scripts/benchmark_load.py
python scripts/backup_db.py --verify-test
```

**Test Suites Covered (`21` test modules, `91` tests):**
- `test_security_audit.py`: Path traversal (`../../.env`) & cross-tenant file isolation, SVG download `nosniff`/`attachment` headers, plan upload caps (`413`), AST sandbox & SSRF defense, 3-tier RBAC boundaries, API key SHA-256 revocation & plan model gates, Stripe HMAC-SHA256 webhook verification, HTTP security headers, GDPR right-to-erasure (`DELETE /api/v1/users/me`), and truthful Gateway zero-masquerading attribution.
- `test_ecosystem_e2e.py`: End-to-end commercial registration -> Free/Pro plan upgrade -> invoice emission -> `nex_live_...` API key minting/rotation/revocation -> `/v1/models`, `/v1/embeddings`, `/v1/chat/completions`, `/v1/completions` -> Admin Control Center management -> Model Lab checkpoint validation & live production promotion -> `/metrics` Prometheus check.
- `test_training_infra.py`: Hardware telemetry (`pynvml`/`nvidia-smi`/PyTorch/`psutil`), ML framework stack inspection & DeepSpeed/NeMo/PEFT configs, license compatibility guard, 10-dimension comparative benchmarks + 5-gram/SHA-256 data leakage prevention, isolated child worker fine-tuning (`lora` pause/resume/validation, `instruction`, `dpo`, `grpo`), SafeTensors checkpoint export/rollback, INT8 dynamic quantization + TTFT benchmarking, and OpenAI-compatible serving (`/v1/models`, `/v1/health`, `/v1/chat/completions`, `/v1/completions`).
- `test_lab.py`: Foundation model registry, analytical parameter counter, RoPE rotary embeddings, RMSNorm, SwiGLU, cross-entropy loss, dataset NFKC normalization, PII scanning, deduplication, BPE tokenizer training and fertility, hardware profiling, and authentic training run execution.
- `test_multimodal.py`: Image upload, OCR, screenshot analysis, video timestamp segmentation.
- `test_voice.py`: Speech-to-text, text-to-speech generation, transcription endpoints.
- `test_tools.py`: Tool registry, execution engine, safety approval gates.
- `test_sandbox.py`: Subprocess code execution sandbox, static AST security validator blocking dangerous operations.
- `test_research.py`: Web research service, content extraction, SSRF security validation.
- `test_documents.py`: Document assistant, multi-format parsing (PDF, DOCX, XLSX, CSV, PPTX), table extraction, cross-document RAG.
- `test_agents.py`: Multi-agent orchestrator, specialized agents (Research, Coding, Vision, Data, Document, Browser).
- `test_auth.py`: Registration, duplicate detection, login, profile, unauthorized guards.
- `test_router.py`: Intelligent model routing across coding, math, fast chat, vision, and manual override.
- `test_gateway.py`: Model registry, health checks, streaming, fallback resilience, structured output.
- `test_memory.py`: Semantic memory store, similarity retrieval, duplicate detection, tenant isolation, deletion.
- `test_rag.py`: Document ingestion, recursive chunking, hybrid BM25 + vector search, RRF reranking, citation correctness.
- `test_context.py`: Token counting, model budgeting, conversation history compression and summarization.
- `test_messages.py`: Streaming SSE responses, editing, feedback, token accounting.
- `test_conversations.py`: CRUD, pin, archive, search.
- `test_isolation.py`: Strict cross-tenant access control.
- `test_llm_provider.py`: Factory instantiation and fallback cascade.
