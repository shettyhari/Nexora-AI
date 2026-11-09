# NEXORA AI – Production Operational Runbooks

**Version:** 2.0.0  

Step-by-step triage and recovery procedures for on-call SREs and platform administrators operating NEXORA AI.

---

## Quick Reference: Key Health & Observability Signals

| Signal | Endpoint / Source | Healthy Threshold |
| :--- | :--- | :--- |
| Reverse Proxy Liveness | `GET /nginx-health` | `200 healthy` |
| Backend Readiness | `GET /health` | `200 {"status": "healthy"}` |
| Prometheus Metrics | `GET /metrics` | `nexora_http_errors_total` steady, `nexora_models_registered >= 1` |
| Admin Infra Health | `GET /api/v1/admin/system-health` | `database.connected=true`, `cache.redis_connected=true`, `storage.writable=true` (or `connected`) |
| LLM Provider Health | `GET /api/v1/admin/providers` | Configured providers report `"status": "online"` |
| OpenAI Serving Worker | `GET /v1/health` (or `/inference-health`) | `status == "healthy"` |

---

## Runbook 1: Upstream LLM Provider Outage or Surge in Fallback Usage

**Symptoms:**
- Elevated `fallback_used: true` notices on `/api/v1/messages` or `nexora_attribution.fallback_used` in `/v1/chat/completions`.
- `/api/v1/admin/providers` reports an external adapter (`openai`, `google`, `anthropic`, `huggingface`) `offline` or degraded.

**Triage & Remediation:**
1. Inspect live adapter health and credential state via **Admin -> Providers & Keys** (`/api/v1/admin/providers`) and error table via `/api/v1/admin/analytics`.
2. Confirm whether the external vendor API key expired/rotated or quota exhausted; note all provider adapters read `settings` dynamically, so updating env secrets and restarting workers picks up new keys cleanly without code edits.
3. Verify `nexora-flagship` and `nexora-fast` remain `active` so traffic degrades gracefully with truthful attribution rather than returning `5xx` errors.
4. If an external model causes excessive timeouts before failover, temporarily disable it via `PATCH /api/v1/admin/models/{model_id}` (`{"is_enabled": false}`) until the vendor stabilizes.

---

## Runbook 2: Isolated Training Worker Crash or Stalled Job

**Symptoms:**
- A job in `/lab` or `/api/v1/admin/training-and-gpu` shows status `failed`, stale heartbeat, or terminated OS PID (`_is_pid_running == False`).

**Triage & Remediation:**
1. Tail worker stdout/stderr logs without touching containers directly:
   ```bash
   GET /api/v1/lab/jobs/{job_id}/logs?tail=200
   ```
   Or inspect `./lab_jobs/<job_id>/` inside `worker-training`.
2. Check host RAM/GPU capacity via `GET /api/v1/admin/training-and-gpu` (`hardware` block). Out-of-memory errors require reducing `batch_size` / `max_seq_len` or enabling `grad_accum_steps` / QLoRA.
3. Recover from the last verified checkpoint:
   ```bash
   POST /api/v1/lab/jobs/{job_id}/recover
   ```
4. Never restart the main FastAPI web workers to fix a training crash; training executes strictly inside isolated subprocesses (`TrainingJobManager`).

---

## Runbook 3: Redis Cache / Rate-Limiter Unreachable

**Symptoms:**
- `/api/v1/admin/system-health` reports `cache.backend: "memory_fallback"`, `redis_connected: false`.
- Rate limiting reverts from shared cross-worker Redis buckets to per-worker in-memory sliding windows (`SlidingWindowRateLimiter`).

**Triage & Remediation:**
1. Check Redis container health & memory:
   ```bash
   docker compose -f docker-compose.prod.yml ps redis
   docker compose -f docker-compose.prod.yml exec redis redis-cli ping
   docker compose -f docker-compose.prod.yml exec redis redis-cli info memory
   ```
2. Check Redis logs for AOF disk full or OOM (`maxmemory 512mb` with `allkeys-lru` eviction).
3. Restart `redis` if hung; FastAPI's `SlidingWindowRateLimiter` automatically resumes distributed Redis enforcement on the next request without restarting `backend`.

---

## Runbook 4: Leaked or Compromised Commercial Developer API Key (`nex_live_...`)

**Symptoms:**
- Abnormal token consumption spike in `/api/v1/admin/overview`, `/api/v1/developer/usage`, or suspicious entries in `/api/v1/admin/security-events` (`invalid_api_key`, `revoked_api_key_attempt`, `rate_limit_exceeded`).

**Triage & Remediation:**
1. Obtain the key ID or owner user from `developer_api_keys` (`key_prefix` is logged safely without exposing secrets).
2. **Immediate Revocation / Rotation:**
   - User or authorized session triggers `POST /api/v1/developer/keys/{key_id}/revoke` or `/rotate`. All cached/subsequent requests using the compromised key immediately fail with `401 This API key has been revoked`.
   - If the compromised account is actively abused by an attacker, suspend the entire user via Admin Control Center (`PATCH /api/v1/admin/users/{user_id}` with `{"is_active": false}`), blocking both JWT sessions and all owned API keys immediately (`get_current_user` & `authenticate_api_principal` reject inactive users with `403`).
3. Audit `AuditLog` (`GET /api/v1/admin/audit-logs`) and `SecurityEvent` (`GET /api/v1/admin/security-events`) for blast radius assessment.

---

## Runbook 5: Database Corruption Alert or Schema Upgrade Failure

**Symptoms:**
- `GET /api/v1/admin/system-health` shows `database.connected: false` or `alembic upgrade head` fails mid-deploy.

**Triage & Remediation:**
1. Inspect DB container logs (`docker compose -f docker-compose.prod.yml logs postgres`) and `alembic current`.
2. Verify latest backup manifest in `/app/backups/`:
   ```bash
   cat /app/backups/*.manifest.json | tail -n 30
   ```
3. Execute restoration using `backend/scripts/backup_db.py --restore <file>` per [`DATABASE_BACKUP_STRATEGY.md`](DATABASE_BACKUP_STRATEGY.md).
4. Re-run `alembic upgrade head` and verify `/health` and `/api/v1/admin/system-health`.

---

## Runbook 6: Stripe Billing Webhook Verification Failures

**Symptoms:**
- Surge of `SecurityEvent` rows with `event_type="invalid_webhook_signature"` and HTTP `400 Invalid webhook signature` responses on `POST /api/v1/billing/webhook`.

**Triage & Remediation:**
1. Verify Stripe Dashboard webhook signing secret (`whsec_...`) matches `STRIPE_WEBHOOK_SECRET` in `.env.production`.
2. Ensure reverse proxy (Nginx) does not alter or re-encode the raw request body before passing to FastAPI (`BillingService.verify_stripe_webhook_signature` signs exact `t=...,v1=...` raw request bytes).
3. If `invalid_webhook_signature` spikes from unfamiliar IPs with non-Stripe payloads, inspect source IPs in `SecurityEvent.ip_address` and block abusive CIDRs at the edge WAF / load balancer.

---

## Runbook 7: Rising `5xx` Error Rate or Latency Spike (`/metrics`)

**Triage & Remediation:**
1. Query `GET /metrics` (`nexora_http_errors_total / nexora_http_requests_total`, `nexora_http_avg_latency_ms`) and inspect recent failing calls in `GET /api/v1/admin/analytics` (`recent_errors`).
2. Check PostgreSQL latency in `GET /api/v1/admin/system-health` (`database.latency_ms`).
3. Check CPU/RAM pressure on host (`hardware` in `/api/v1/admin/system-health`). If `backend` is saturating 4 workers on large file/video processing, ensure heavy ML jobs execute exclusively via isolated workers.
