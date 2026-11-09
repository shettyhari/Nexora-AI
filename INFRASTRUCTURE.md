# NEXORA AI – Production Infrastructure Architecture

**Version:** 2.0.0  
**Last Verified:** 2026-11-09  

This document describes the production container topology, network isolation, reverse-proxy routing, observability endpoints, and CI/CD validation pipeline implemented in NEXORA AI.

---

## 1. Multi-Service Topology & Network Segmentation

NEXORA separates public edge traffic from internal storage and isolated Model Lab compute workloads across two Docker bridge networks defined in [`docker-compose.prod.yml`](docker-compose.prod.yml) (and profile-gated development workers in [`docker-compose.yml`](docker-compose.yml)).

```text
                       Internet / Clients
                               │
                     ┌─────────▼─────────┐
                     │   Nginx Proxy     │  ports: 80, 443
                     │ (nginx:1.27-alpine│  networks: nexora_edge, nexora_internal
                     └────┬─────────┬────┘
                          │         │
          nexora_edge     │         │  nexora_edge + nexora_internal
         ┌────────────────▼──┐   ┌──▼────────────────────┐
         │     Frontend      │   │     Backend API       │  FastAPI (--workers 4)
         │ Next.js (Port 3000)│   │ Uvicorn (Port 8000)   │  alembic upgrade head
         └───────────────────┘   └─┬───────────────────┬─┘
                                   │  nexora_internal  │  (never publicly routed)
         ┌─────────────────────────┼───────────────────┼─────────────────────────┐
         │                         │                   │                         │
┌────────▼────────┐       ┌────────▼────────┐ ┌────────▼────────┐       ┌────────▼────────┐
│  PostgreSQL 16  │       │     Redis 7     │ │ Worker Training │       │Worker Inference │
│  (Port 5432)    │       │  (AOF + LRU)    │ │(NEXORA_IN_ML_   │       │  OpenAI Engine  │
│                 │       │                 │ │ WORKER=1,       │       │  (Port 8001,    │
│                 │       │                 │ │ no-new-privs)   │       │  RO checkpoints)│
└─────────────────┘       └─────────────────┘ └─────────────────┘       └─────────────────┘
```

### Service Inventory

| Service | Image / Build | Exposed Host Ports | Networks | Resource Limits (`docker-compose.prod.yml`) |
| :--- | :--- | :--- | :--- | :--- |
| `nginx` | `nginx:1.27-alpine` | `80`, `443` | `nexora_edge`, `nexora_internal` | Edge reverse proxy |
| `frontend` | `frontend/Dockerfile` (`node:20-alpine`) | None in prod (`3000` in dev) | `nexora_edge` | `1G` RAM |
| `backend` | `backend/Dockerfile` (`python:3.12-slim`) | None in prod (`8000` in dev) | `nexora_edge`, `nexora_internal` | `2G` RAM, 4 Uvicorn workers |
| `postgres` | `postgres:16-alpine` | None in prod (`5432` in dev) | `nexora_internal` | Persistent volume `postgres_prod_data` |
| `redis` | `redis:7-alpine` (`appendonly yes`, `maxmemory 512mb`) | None in prod (`6379` in dev) | `nexora_internal` | Persistent volume `redis_prod_data` |
| `worker-training` | `backend/Dockerfile.worker` (`python:3.11-slim`) | None (strictly isolated) | `nexora_internal` | `8G` RAM, `no-new-privileges:true` |
| `worker-inference` | `backend/Dockerfile.worker` (`python:3.11-slim`) | None in prod (`8001` in dev) | `nexora_internal` | `4G` RAM, `:ro` mounted weights |

---

## 2. Isolated ML Training & Inference Worker Separation

User-facing web API processes use the slim Python 3.12 environment (`backend/requirements.txt`), keeping cold starts fast and Vercel-compatible. Heavy deep learning frameworks (`torch`, `transformers`, `accelerate`, `peft`, `trl`, `safetensors`) are installed in `backend/Dockerfile.worker` (`backend/requirements-training.txt`) and localized via [`backend/app/lab/runtime_bridge.py`](backend/app/lab/runtime_bridge.py).

- **Subprocess Worker Isolation:** Training jobs (`TrainingJobManager`) NEVER run gradient updates inside FastAPI HTTP handlers; they spawn child worker processes (`NEXORA_IN_ML_WORKER=1`) with PID tracking, filesystem job logs (`./lab_jobs/<job_id>`), and privilege hardening (`no-new-privileges:true` in Compose).
- **Read-Only Inference Mounts:** `worker-inference` mounts `./backend/lab_checkpoints` and `./backend/lab_optimized` read-only (`:ro`), preventing an inference process from mutating stored model artifacts.
- **Commercial API Gating:** External clients never contact `worker-inference` directly; `/v1/*` traffic passes through FastAPI's `authenticate_api_principal` and `BillingService` gates first.

---

## 3. Edge Reverse Proxy & SSE Streaming (`infra/nginx.conf`)

[`infra/nginx.conf`](infra/nginx.conf) enforces production ingress policies:

- **Upload Limits:** `client_max_body_size 50m;` matching `Settings.MAX_FILE_SIZE_MB = 50`.
- **Edge Rate-Limit Zones (Defense-in-Depth alongside FastAPI Redis `SlidingWindowRateLimiter`):**
  - `auth_limit`: `30r/m` (`burst=15 nodelay`) on `/api/v1/auth/`
  - `api_limit`: `120r/m` (`burst=40` on `/api/v1/messages`, `burst=60` on `/v1/` and `/api|/health|/metrics`)
- **Zero-Buffer SSE Streaming:** Both `/api/v1/messages` and `/v1/` disable `proxy_buffering` and `proxy_cache`, enable `chunked_transfer_encoding on`, set `proxy_http_version 1.1` with empty `Connection ""`, and raise `proxy_read_timeout` / `proxy_send_timeout` to `300s` for long reasoning streams.
- **Global Security Headers:** Injects `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Permissions-Policy: camera=(), microphone=(self), geolocation=()` alongside FastAPI's HTTP security middleware.
- **Health Endpoints:**
  - `/nginx-health` — reverse proxy liveness (`200 healthy`)
  - `/health` & `/api/health` — FastAPI service readiness
  - `/inference-health` — proxies `/v1/health` on `worker-inference`

---

## 4. Storage, Cache & Observability

### Object Storage (`backend/app/services/storage/object_storage.py`)
- **`local` backend (default dev/single-node):** Writes uploads inside realpath-confined `UPLOAD_DIR` after `sanitize_filename` and extension validation.
- **`s3` backend (`STORAGE_BACKEND=s3`):** Uses `boto3` targeting AWS S3, Cloudflare R2, or MinIO via `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, and `S3_REGION`. Falls back cleanly to local confined storage if `boto3` or credentials are unavailable.
- Health telemetry is surfaced via `/api/v1/admin/system-health` (`backend`, `status`, `writable`, `local_dir`, `s3_bucket`).

### Distributed Caching & Rate Limiting (`backend/app/core/rate_limiter.py`)
- `SlidingWindowRateLimiter` executes atomic fixed-slot `INCR` + `EXPIRE` counters in Redis (`nexora:rl:{bucket_key}:{window_slot}`) when `cache._redis` is connected.
- Automatically fails over to an `asyncio.Lock`-protected in-memory sliding `deque` per worker if Redis is disabled (`REDIS_ENABLED=false`) or unreachable.

### Prometheus & Admin Observability
- **`GET /metrics` (`text/plain`):** Exposes `nexora_http_requests_total`, `nexora_http_errors_total`, `nexora_http_avg_latency_ms`, `nexora_models_registered`, and `nexora_process_uptime_seconds`.
- **Admin Control Center (`/admin` -> `/api/v1/admin/*`):** Aggregates PostgreSQL/SQLite query latency, Redis ping health, real CPU/RAM/Disk/GPU telemetry (`HardwareTelemetryMonitor`), LLM Gateway provider health, token cost analytics, `SecurityEvent` logs, and `AuditLog` entries.

---

## 5. Multi-Service Vercel Architecture (`vercel.json`)

NEXORA preserves zero-friction deployment on Vercel via [`vercel.json`](vercel.json):
- `backend` service (`root: "backend"`, `framework: "fastapi"`) installs lean dependencies from `backend/requirements.txt`.
- `frontend` service (`root: "frontend"`, `framework: "nextjs"`) receives the internal `BACKEND_URL` binding automatically.
- Top-level rewrites route `/api/(.*)` to `backend` and `/(.*)` to `frontend`.

---

## 6. Continuous Integration Pipeline (`.github/workflows/ci.yml`)

Every push to `main` or `staging` and pull request to `main` triggers three CI jobs:
1. **`backend-verify`:** Sets up Python 3.12, runs `alembic upgrade head` against a clean database (`001` through `006_production_ecosystem`), and executes the full `pytest -v` test suite (Core, Model Lab, Training Infra, Security Audit, Ecosystem E2E).
2. **`frontend-verify`:** Sets up Node.js 20, installs via `npm ci`, and validates TypeScript + Next.js App Router bundle compilation via `npm run build`.
3. **`infra-validate`:** Validates `docker-compose.yml` and `docker-compose.prod.yml` schemas (`docker compose config -q`) and tests `infra/nginx.conf` syntax via `nginx:1.27-alpine nginx -t`.
