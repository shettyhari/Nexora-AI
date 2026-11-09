# NEXORA AI – Performance & Benchmark Report

**Version:** 2.0.0  
**Measurement Date:** 2026-11-09  
**Benchmark Runner:** [`backend/scripts/benchmark_load.py`](backend/scripts/benchmark_load.py)  

---

## 1. Benchmark Methodology & Measurement Scope

All figures in this report were **directly measured on the local host runtime** using [`backend/scripts/benchmark_load.py`](backend/scripts/benchmark_load.py). Zero synthetic, estimated, or extrapolated numbers are presented as measured metrics.

### Execution Environment
- **HTTP Transport:** In-process `httpx.AsyncClient(transport=ASGITransport(app=app))` executing the complete FastAPI middleware stack (HTTP security headers, Prometheus telemetry counters, auth dependencies, SQLAlchemy 2.0 async ORM, Billing gatekeeper, Gateway, RAG, and Document parser).
- **Database Engine:** Isolated temporary `sqlite+aiosqlite` instance (`REDIS_ENABLED=false`, `RATE_LIMIT_ENABLED=false` to isolate request-path latency rather than hitting 429 intentionally).
- **Inference Execution Path:** Built-in deterministic `nexora-fast` neural engine (`NexoraProvider`), excluding external network vendor variance (`OpenAI`/`Anthropic`/`Gemini`) so measurements reflect NEXORA platform overhead cleanly.
- **UI & Test Suites Also Verified:** Full **91-test** `pytest -v` backend suite (`91 passed, 0 failed in 234.96s`) and Next.js production build (`npm --prefix frontend run build`, all 12 App Router routes compiled).

---

## 2. Measured Host Hardware Telemetry (`HardwareTelemetryMonitor`)

| Metric | Measured Value |
| :--- | :--- |
| **Operating System** | Windows 11 (AMD64) |
| **Accelerator Status** | `cpu` (`GPU Unavailable — No CUDA/MPS hardware accelerator detected (CPU compute active)`) |
| **GPU Count / CUDA** | `0` / `null` |
| **PyTorch Version** | `2.15.0+cpu` |
| **CPU Cores** | `4` physical / `8` logical (`1505.0 MHz`, `13.0%` utilization at snapshot) |
| **System RAM** | `7.72 GB` total (`6.90 GB` used / `0.82 GB` free — `89.4%` utilization at snapshot) |
| **System Disk** | `237.17 GB` total (`44.35 GB` free) |

---

## 3. HTTP Endpoint Latency & Concurrency Scaling

Tested across **30 requests per concurrency tier** (`c=1`, `c=10`, `c=25`) for `GET /health`, `GET /api/v1/models`, and `POST /v1/embeddings`, and **20 requests per concurrency tier** (`max_tokens=24`) for `POST /v1/chat/completions`. **Error rate was `0.0%` across every concurrency tier.**

| Endpoint | Concurrency | Reqs | Errors | Wall Time (s) | Throughput (RPS) | Min (ms) | Mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Max (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `GET /health` | `c=1` | 30 | 0 (0.0%) | 0.0468 | 640.82 | 1.256 | 1.533 | 1.545 | 1.801 | 2.029 | 2.115 |
| `GET /health` | `c=10` | 30 | 0 (0.0%) | 0.0416 | 720.30 | 5.592 | 8.794 | 8.744 | 12.387 | 13.254 | 13.442 |
| `GET /health` | `c=25` | 30 | 0 (0.0%) | 0.0367 | 817.52 | 3.414 | 16.332 | 17.571 | 24.093 | 24.765 | 24.956 |
| `GET /api/v1/models` | `c=1` | 30 | 0 (0.0%) | 0.4481 | 66.95 | 11.969 | 14.903 | 14.693 | 16.849 | 17.395 | 17.538 |
| `GET /api/v1/models` | `c=10` | 30 | 0 (0.0%) | 0.7577 | 39.59 | 74.478 | 234.463 | 212.844 | 372.906 | 376.638 | 377.631 |
| `GET /api/v1/models` | `c=25` | 30 | 0 (0.0%) | 0.4995 | 60.06 | 176.699 | 332.129 | 316.124 | 454.584 | 458.715 | 458.816 |
| `POST /v1/embeddings` | `c=1` | 30 | 0 (0.0%) | 1.0863 | 27.62 | 26.886 | 36.169 | 31.324 | 40.403 | 123.252 | 156.296 |
| `POST /v1/embeddings` | `c=10` | 30 | 0 (0.0%) | 1.4579 | 20.58 | 72.944 | 400.892 | 215.333 | 1205.542 | 1354.920 | 1361.482 |
| `POST /v1/embeddings` | `c=25` | 30 | 0 (0.0%) | 1.3520 | 22.19 | 242.340 | 712.563 | 628.869 | 1249.998 | 1323.126 | 1348.908 |
| `POST /v1/chat/completions` | `c=1` | 20 | 0 (0.0%) | 0.5998 | 33.34 | 27.130 | 29.942 | 29.793 | 32.409 | 34.171 | 34.612 |
| `POST /v1/chat/completions` | `c=10` | 20 | 0 (0.0%) | 0.9042 | 22.12 | 30.651 | 301.291 | 179.557 | 793.739 | 875.540 | 895.990 |
| `POST /v1/chat/completions` | `c=25` | 20 | 0 (0.0%) | 1.0212 | 19.59 | 220.280 | 585.959 | 557.740 | 954.109 | 1004.398 | 1016.970 |

---

## 4. End-to-End SSE Chat Streaming (`POST /api/v1/messages`)

Measured across **10 sequential streaming runs** executing the full 8-Stage Reasoning Orchestrator (task profiling, context window budgeting, gateway dispatch, token SSE delivery, `Message` / `UsageRecord` / `ApiUsageLog` persistence, and billing quota deduction):

| Phase | Samples | Errors | Min (ms) | Mean (ms) | p50 (ms) | p95 (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Time to First Token (TTFT)** | 10 | 0 (0.0%) | 92.71 | 147.03 | 101.22 | 341.707 |
| **End-to-End Stream Completion (E2E)** | 10 | 0 (0.0%) | 92.75 | 147.08 | 101.271 | 341.76 |

*Note:* The first cold iteration includes lazy SQLAlchemy/BM25/service warm-up (`p95 ~341.7 ms`), while warm SSE TTFT settles near **`101.2 ms` (median)**.

---

## 5. Core Subsystem Micro-Benchmarks

### RAG Hybrid Retrieval (`BM25Okapi` + Dense Vectors + RRF $k=60$)
- **Corpus Size:** 40 chunks ingested via `rag_service.ingest_document`
- **40-Chunk Ingest + Embedding Time:** **`61.85 ms`**
- **Hybrid Search Latency (15 queries, `top_k=5`):**
  - Mean: **`7.625 ms`**
  - Median (`p50`): **`7.816 ms`**
  - `p95`: **`9.724 ms`**

### Document Intelligence CSV Parsing (`1,000` Rows)
`DocumentIntelligenceService.parse_file()` reads tabular CSV files, normalizes cell values, captures headers/row statistics into a compact summary string (`parsed.text_content`), and materializes all structured rows in `parsed.tables[0].rows`:
- **Runs:** 10 iterations over a 1,000-row CSV (`5` columns)
- **Mean Parse Time:** **`4.718 ms`**
- **`p95` Parse Time:** **`5.788 ms`**
- **Measured Extraction Throughput:** **`211,934.5 rows/s`** (`len(parsed.tables[0].rows) == 1000`)

---

## 6. Bottleneck Analysis & Production Scaling Recommendations

1. **SQLite Single-Writer Serialization Under High Concurrency:**
   - On `GET /health` (zero DB queries), throughput scaled cleanly from `640.82 RPS` (`c=1`) to `817.52 RPS` (`c=25`) with `p95 = 24.09 ms`.
   - On DB-backed endpoints (`POST /v1/embeddings`, `POST /v1/chat/completions`, `GET /api/v1/models`), `c=1` latency was `14.90 ms–36.17 ms` (`p95 <= 40.40 ms`), whereas `c=25` p95 rose to `454.58 ms–1250.00 ms` due to local SQLite single-writer lock serialization across subscription/billing/usage updates in an in-process single-worker loop.
   - **Production Remedy:** Use **PostgreSQL 16 + asyncpg connection pooling + Redis 7** alongside **4 Uvicorn workers** as configured in [`docker-compose.prod.yml`](docker-compose.prod.yml).
2. **Memory Headroom & Isolated ML Workers:**
   - The local dev laptop was running at `89.4%` of `7.72 GB` RAM without CUDA GPUs. Production stacks isolate PyTorch/Transformers/PEFT training & model serving into `worker-training` (`8G` limit) and `worker-inference` (`4G` limit) so the API tier (`backend`, `2G` limit) stays insulated from ML memory spikes.
3. **Zero-Buffer Proxy Streaming:**
   - [`infra/nginx.conf`](infra/nginx.conf) disables `proxy_buffering` and `proxy_cache` on `/api/v1/messages` and `/v1/`, preserving low SSE TTFT across load-balanced edge ingress.

---

## 7. Reproducing This Benchmark

Run cleanly against a fresh temporary SQLite database directory (does not modify dev databases):
```bash
cd backend
python scripts/benchmark_load.py
```
