# NEXORA AI – Production Deployment Guide

**Version:** 2.0.0  

This guide covers end-to-end deployment of NEXORA AI across Docker Compose (Production/Staging), bare-metal/VM environments, and Vercel Multi-Services (`vercel.json`).

---

## 1. Environment Configuration Matrix

Templates live at the repository root and MUST NEVER have live credentials committed to Git:

| File | Purpose | Secret Validation | Default DB & Storage |
| :--- | :--- | :--- | :--- |
| [`.env.example`](.env.example) | Local development / quickstart | `STRICT_SECRET_VALIDATION=false` | SQLite (`nexora.db`), `local` storage, `local` billing |
| [`.env.staging.example`](.env.staging.example) | Pre-production staging mirror | `STRICT_SECRET_VALIDATION=true` | PostgreSQL `nexora_staging`, S3 staging bucket, Stripe test |
| [`.env.production.example`](.env.production.example) | Commercial production cluster | `ENVIRONMENT=production` (`true` enforced) | PostgreSQL 16 `nexora_prod`, Redis 7, S3/R2, live Stripe |

### Mandatory Security Guard (`validate_production_secrets`)
At startup (`backend/app/main.py` lifespan), `Settings.validate_production_secrets()` checks:
1. `SECRET_KEY` is NOT the built-in development placeholder.
2. `SECRET_KEY` length is at least **32 characters** (generate via `openssl rand -hex 32`).

When `ENVIRONMENT=production` or `STRICT_SECRET_VALIDATION=true`, failing either check raises a fatal `RuntimeError` before accepting traffic.

### Core Production Environment Variables
```bash
ENVIRONMENT=production
STRICT_SECRET_VALIDATION=true
SECRET_KEY=<64-hex-char-secret>
POSTGRES_DB=nexora_prod
POSTGRES_USER=nexora_prod
POSTGRES_PASSWORD=<strong-db-password>
DATABASE_URL=postgresql+asyncpg://nexora_prod:<strong-db-password>@postgres:5432/nexora_prod
REDIS_URL=redis://redis:6379/0
REDIS_ENABLED=true
CORS_ORIGINS=https://nexora.ai,https://app.nexora.ai
NEXT_PUBLIC_API_URL=https://api.nexora.ai
```

Optional Commercial Integrations:
- **AI Providers:** `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `HUGGINGFACE_API_KEY`, `OPENAI_COMPATIBLE_BASE_URL` (missing keys safely trigger truthful fallback to `nexora-flagship` unless disabled).
- **Web Search:** `TAVILY_API_KEY` or `SERPAPI_API_KEY`.
- **Stripe Billing:** `PAYMENT_PROVIDER=stripe`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (required for `Stripe-Signature` HMAC-SHA256 verification at `POST /api/v1/billing/webhook`).
- **S3 / R2 Object Storage:** `STORAGE_BACKEND=s3`, `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION`.

---

## 2. Production Deployment via Docker Compose

### Step 1: Prepare Production Secrets
```bash
cp .env.production.example .env.production
# Generate SECRET_KEY with: openssl rand -hex 32
# Edit .env.production with live PostgreSQL password, CORS_ORIGINS, Stripe, S3, and provider keys.
export POSTGRES_PASSWORD="<same-password-as-in-.env.production>"
```

### Step 2: Validate Compose Configuration
```bash
docker compose -f docker-compose.prod.yml config -q
```

### Step 3: Build & Launch Stack
```bash
docker compose -f docker-compose.prod.yml up -d --build
```
Startup order enforced via healthchecks:
1. `postgres` (`pg_isready`) and `redis` (`redis-cli ping`) start on `nexora_internal`.
2. `backend` runs `alembic upgrade head` (migrations `001` -> `006_production_ecosystem`) and boots Uvicorn with 4 workers.
   - `lifespan()` seeds default models, idempotently seeds Free/Pro/Enterprise `SubscriptionPlan` tiers, and synchronizes approved `PublishedModel` entries into `ModelRegistry`.
3. `worker-training` (strictly isolated on `nexora_internal` with `no-new-privileges:true`) and `worker-inference` (`uvicorn ... --port 8001 --workers 2`, `:ro` checkpoint mounts) initialize.
4. `frontend` builds Next.js production assets and starts on internal port `3000`.
5. `nginx` exposes ports `80` / `443` with rate limits, security headers, and zero-buffer SSE streaming.

### Step 4: Verify Production Health
```bash
curl -fsS http://localhost/nginx-health
curl -fsS http://localhost/health
curl -fsS http://localhost/metrics
curl -fsS http://localhost/inference-health
```

---

## 3. Initial Admin Provisioning & RBAC Verification

New registrations via `POST /api/v1/auth/register` receive `role="user"` and auto-assign the `free` plan on first entitlement check. Promote your initial administrator directly in PostgreSQL after first signup:
```sql
UPDATE users SET role = 'admin', is_verified = true WHERE email = 'cto@nexora.ai';
```
Once signed in as an admin:
- Open `/admin` in the web UI (or call `GET /api/v1/admin/overview`, `/api/v1/admin/system-health`).
- Promote ML team members to `researcher` via **Admin -> Users & RBAC** so they can access `/lab` while remaining barred from `/admin`.

---

## 4. Database Migrations & Rollback Safety

```bash
# Before upgrading: snapshot current DB
docker compose -f docker-compose.prod.yml exec backend \
  python scripts/backup_db.py --database-url "$DATABASE_URL" --backup-dir /app/backups --backup --prune 14

# Apply migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Check active revision
docker compose -f docker-compose.prod.yml exec backend alembic current
```

---

## 5. Vercel Multi-Services Deployment

NEXORA AI supports serverless deployment on Vercel using [`vercel.json`](vercel.json):
1. Connect `https://github.com/shettyhari/Nexora-AI` in the Vercel dashboard (multi-services enabled).
2. Configure managed external **PostgreSQL** (`DATABASE_URL=postgresql+asyncpg://...`) and **Redis** (`REDIS_URL=redis://...`) in Vercel Project Environment Variables.
3. Set `ENVIRONMENT=production`, `STRICT_SECRET_VALIDATION=true`, a strong `SECRET_KEY`, and external S3 storage (`STORAGE_BACKEND=s3`) because serverless filesystem storage is ephemeral.
4. Keep `backend/requirements.txt` lean (training stack lives in `backend/requirements-training.txt`); Vercel builds `backend` (FastAPI) and `frontend` (Next.js) concurrently, binding `BACKEND_URL` automatically and rewriting `/api/(.*)` -> `backend` and `/(.*)` -> `frontend`.

---

## 6. Post-Deploy Verification Checklist
- [ ] `GET /health` returns `"status": "healthy"`, `"environment": "production"`, `"version": "2.0.0"`.
- [ ] `GET /metrics` returns Prometheus counters with `200 OK`.
- [ ] `GET /api/v1/billing/plans` returns `free`, `pro`, and `enterprise`.
- [ ] `POST /api/v1/billing/webhook` without `Stripe-Signature` returns `400` and creates a `SecurityEvent`.
- [ ] Non-admin access to `/api/v1/admin/overview` returns `403 Forbidden`.
- [ ] Response headers on `/health` include `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY`.
