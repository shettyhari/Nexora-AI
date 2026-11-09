# NEXORA AI – Release Notes (`v2.0.0`)

**Release Date:** 2026-11-09  
**Codename:** Production-Grade Independent Commercial AI Ecosystem (Prompt 6)  
**Alembic Head Revision:** `006_production_ecosystem`  
**Verification Status:** `91/91` Backend Tests Passing (`pytest -v`) • `12/12` Next.js Routes Built Cleanly • Backup Restore Drill Passed • Security Audit Verified  

---

## Summary

`v2.0.0` unifies all six phases of NEXORA AI—the ChatGPT-style workspace (Prompt 1), Unified Model Gateway & Router (Prompt 2), Multimodal & Multi-Agent Intelligence (Prompt 3), Proprietary Foundation Model Lab (Prompt 4), Distributed Training & GPU Serving Infrastructure (Prompt 5), and Commercial Billing, Developer API Keys, RBAC, Admin Control Center, Security Hardening, Observability, and Multi-Container Production Deployment (Prompt 6)—into a cohesive, deployable ecosystem while preserving full backward compatibility and Vercel multi-service support ([`vercel.json`](vercel.json)).

---

## Major Features & Architecture Additions

### 1. Commercial Database Schema & Migrations (`006_production_ecosystem`)
Added [`backend/alembic/versions/006_production_ecosystem.py`](backend/alembic/versions/006_production_ecosystem.py) and ORM models in [`backend/app/models/ecosystem.py`](backend/app/models/ecosystem.py):
- `subscription_plans` — Commercial Free (`\$0`, `250k` tokens/mo, `20 RPM`, `10 MB` uploads), Pro (`\$29/mo` or `\$290/yr`, `5M` tokens/mo, `60 RPM`, `50 MB` uploads, API keys), and Enterprise (`\$199/mo` or `\$1,990/yr`, `50M` tokens/mo, `300 RPM`, `250 MB` uploads) tiers.
- `user_subscriptions` & `billing_invoices` — Monthly/annual cycle tracking, automatic period reset, cancellation scheduling, invoice numbering (`INV-YYYYMMDD-...`), and provider abstraction.
- `developer_api_keys` — Cryptographic `nex_live_...` keys with **SHA-256** hashed storage (`key_hash`), prefix masking, scoped permissions, expiration dates, revocation, and rotation tracking.
- `api_usage_logs` — Per-request token, cost (`cost_usd`), latency (`latency_ms`), model, provider, status code, and error attribution.
- `security_events` — Persistent forensic audit stream recording path traversal attempts, invalid/revoked API keys, RBAC violations, invalid Stripe signatures, and rate-limit breaches.
- `published_models` — Dynamic catalog syncing approved proprietary Model Lab checkpoints and admin configuration overrides into live traffic.

### 2. Commercial Billing, Quotas & Developer OpenAI Platform (`/billing`, `/developer`, `/v1/*`)
- **Billing & Subscriptions (`/api/v1/billing/*` + [`/billing`](frontend/src/app/billing/page.tsx)):** Plan browsing, instant upgrade/downgrade, immediate or end-of-period cancellation, invoice receipts, and Stripe HMAC-SHA256 webhook verification (`POST /api/v1/billing/webhook`).
- **Quota & RPM Gatekeeper (`BillingService.enforce_request_gates`):** Enforces plan RPM rate limits (`SlidingWindowRateLimiter` via Redis `INCR`/`EXPIRE` with in-memory fallback), monthly token balance, per-plan upload caps (`413 Payload Too Large`), and model access entitlements before execution.
- **Developer Portal (`/api/v1/developer/*` + [`/developer`](frontend/src/app/developer/page.tsx)):** Self-service API key minting (plaintext displayed once), atomic key rotation, instant revocation, and live token/cost/latency consumption dashboard.
- **Commercial OpenAI-Compatible API (`/v1/models`, `/v1/embeddings`, `/v1/chat/completions`, `/v1/completions`, `/v1/health`):** Supports standard Bearer `nex_live_...` or `X-API-Key` credentials, full token & cost accounting, streaming `[DONE]` SSE chunks, and `nexora_attribution` metadata.

### 3. Administration Control Center & Model Lab Publishing Bridge (`/admin`)
- Added [`backend/app/api/v1/admin.py`](backend/app/api/v1/admin.py) (14 strictly `require_admin`-gated routes) and interactive multi-tab UI at [`/admin`](frontend/src/app/admin/page.tsx):
  - Executive KPI overview (users, billing revenue, API tokens/latency/errors, active keys, Lab workers, security events).
  - Live user RBAC (`user` / `researcher` / `admin`) & subscription tier overrides.
  - Dynamic plan pricing/quota updates and live model enable/disable + pricing adjustments.
  - **Lab-to-Production Promotion Bridge:** `POST /api/v1/admin/models/publish-checkpoint` & `POST /api/v1/lab/checkpoints/{id}/publish` validate checkpoint SHA-256 integrity, zero NaN/Inf weights, and forward pass before publishing directly to `PublishedModel` and `ModelRegistry` with zero downtime.
  - Real-time provider credential checks (booleans only—secrets never leaked), GPU/CPU hardware & object storage health, forensic `SecurityEvent` monitor, and compliance `AuditLog` browser.

### 4. End-to-End Security Audit & Truthful Gateway Attribution Fixes
- **File Confinement & Safe Downloads:** Added `resolve_safe_file_path()` & `is_path_within_base()` in [`security_guards.py`](backend/app/core/security_guards.py); added active extension blocklist (`FORBIDDEN_UPLOAD_EXTENSIONS`) and `X-Content-Type-Options: nosniff` + `Content-Disposition: attachment` headers on scriptable attachments such as `.svg`.
- **RBAC Isolation:** Separated regular users (`user`), ML researchers (`researcher` -> `/lab`), and admins (`admin` -> `/admin`), failing closed with `401`/`403` and persisting forensic `SecurityEvent` rows across HTTP errors.
- **Python 3.12 Gateway Attribution Fix:** Resolved `(str, Enum)` dictionary key lookup mismatch (`ModelProvider.value`) and switched provider adapters (`OpenAI`, `Gemini`, `Anthropic`, `HuggingFace`, `OpenAICompatible`) to dynamic `@property` secret lookups. Guaranteed **zero masquerading**: failover always declares explicit `resolved_model`, `actual_provider`, `fallback_used`, and `fallback_from_model`.
- **Checkpoint Checksum Alignment:** Fixed `TrainingRunner.execute_training_run()` to write full weight payloads matching `weights_sha256` on disk.
- **HTTP Security Headers & Secret Validation:** Added global middleware (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, HSTS in production) plus startup `validate_production_secrets()` check and GDPR `DELETE /api/v1/users/me` physical+logical data purge.

### 5. Production Infrastructure, Observability & Disaster Recovery
- Added [`docker-compose.prod.yml`](docker-compose.prod.yml) (Nginx, Frontend, Backend, PostgreSQL 16, Redis 7, isolated `worker-training`, read-only `worker-inference`), [`backend/Dockerfile.worker`](backend/Dockerfile.worker), [`infra/nginx.conf`](infra/nginx.conf), [`.env.staging.example`](.env.staging.example), [`.env.production.example`](.env.production.example), and [`.github/workflows/ci.yml`](.github/workflows/ci.yml).
- Added [`ObjectStorageService`](backend/app/services/storage/object_storage.py) (`s3`/`boto3` with local confined fallback), Prometheus `GET /metrics` endpoint, [`backend/scripts/backup_db.py`](backend/scripts/backup_db.py) (verified SQLite online backup + PostgreSQL `pg_dump`/`pg_restore` + SHA-256 manifests), and [`backend/scripts/benchmark_load.py`](backend/scripts/benchmark_load.py).
- Authored 8 comprehensive operational documents: [`PRODUCTION_DEPLOYMENT.md`](PRODUCTION_DEPLOYMENT.md), [`INFRASTRUCTURE.md`](INFRASTRUCTURE.md), [`DATABASE_BACKUP_STRATEGY.md`](DATABASE_BACKUP_STRATEGY.md), [`MODEL_DEPLOYMENT.md`](MODEL_DEPLOYMENT.md), [`SECURITY_AUDIT_REPORT.md`](SECURITY_AUDIT_REPORT.md), [`PERFORMANCE_REPORT.md`](PERFORMANCE_REPORT.md), [`OPERATIONAL_RUNBOOKS.md`](OPERATIONAL_RUNBOOKS.md), and updated [`API_DOCS.md`](API_DOCS.md).

---

## Upgrade & Migration Instructions

1. Ensure strong `SECRET_KEY` (`openssl rand -hex 32`) is set when `ENVIRONMENT=production` or `STRICT_SECRET_VALIDATION=true`.
2. Capture a pre-migration database snapshot:
   ```bash
   python backend/scripts/backup_db.py --database-url "$DATABASE_URL" --backup-dir /app/backups --backup --prune 14
   ```
3. Run Alembic migrations:
   ```bash
   cd backend && alembic upgrade head
   ```
4. Launch or redeploy the application stack; startup lifespan automatically seeds default `SubscriptionPlan` tiers and synchronizes any approved `PublishedModel` entries.
