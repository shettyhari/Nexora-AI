# NEXORA AI – Database Backup, Restore & Disaster Recovery Strategy

**Version:** 2.0.0  
**Utility Script:** [`backend/scripts/backup_db.py`](backend/scripts/backup_db.py)  

---

## 1. Backup Architecture & Guarantees

NEXORA AI supports both **PostgreSQL 16** (production deployments) and **SQLite** (local/quickstart deployments) through a unified CLI utility (`backend/scripts/backup_db.py`) featuring cryptographic integrity checks and retention management:

1. **PostgreSQL Production Backups (`pg_dump --format=custom`):**
   - Invokes native `pg_dump` in PostgreSQL custom archive format (`.dump`), producing compressed, transactionally consistent snapshots safe during active traffic.
   - Normalized from async DSN (`postgresql+asyncpg://...` -> `postgresql://...`).
2. **SQLite Hot Online Backups (`sqlite3.Connection.backup()`):**
   - Uses SQLite's online Backup API rather than naive file copies, safely copying live WAL/journaled databases without lock corruption.
   - Immediately executes `PRAGMA integrity_check;` on the resulting `.db` snapshot and aborts if the result is not `"ok"`.
3. **SHA-256 Tamper Detection Manifests (`.manifest.json`):**
   - Every backup generates a sibling `<backup_file>.manifest.json` containing `engine`, `sha256` (streamed 64 KB chunks), `size_bytes`, `integrity_check` (SQLite), and UTC ISO timestamp.
   - Before restoring any SQLite backup, `restore_sqlite()` recomputes SHA-256 and **refuses the restore** with a `RuntimeError` if checksums diverge.
4. **Automatic Retention Pruning (`--prune N`):**
   - Keeps the `N` newest `.db` / `.dump` files sorted by modification time and removes older snapshots along with their `.manifest.json` sidecars.

---

## 2. Database Migration History (Alembic)

Schema changes are versioned in `backend/alembic/versions/`:
1. `001_initial_schema` — Users, profiles, preferences, conversations, messages, attachments, projects, memories, RAG collections/documents/chunks, feedback, usage, audit logs.
2. `002_intelligence_engine` — Unified model gateway configurations and routing metadata.
3. `003_multimodal_agents` — Multimodal jobs (`media_jobs`), agent workflows, tool executions.
4. `004_model_lab` — Foundation Model Lab models, datasets, tokenizers, experiments, checkpoints, evaluations.
5. `005_training_infrastructure` — Isolated training jobs, 10-dimension benchmark suites, quantization optimizations, inference deployments.
6. `006_production_ecosystem` — Commercial `subscription_plans`, `user_subscriptions`, `billing_invoices`, `developer_api_keys`, `api_usage_logs`, `security_events`, and `published_models`.

Always capture a verified snapshot **before** executing `alembic upgrade head` in staging or production.

---

## 3. CLI Operations Guide

### Run Automated Backup & Restore Drill (Verified on Host)
```bash
cd backend
python scripts/backup_db.py --verify-test
```
**Verified Execution Output (2026-11-09):** `backup_sqlite` created a snapshot, verified `integrity_check: "ok"` and SHA-256 digest, restored to an isolated target DB via `restore_sqlite`, and confirmed row-level recovery (`"status": "PASSED"`).

### Create Production PostgreSQL Backup (Keep Last 14 Snapshots)
```bash
python backend/scripts/backup_db.py \
  --database-url "$DATABASE_URL" \
  --backup-dir /app/backups \
  --backup \
  --prune 14
```

### Inside Docker Production Stack
```bash
docker compose -f docker-compose.prod.yml exec backend \
  python scripts/backup_db.py --database-url "$DATABASE_URL" --backup-dir /app/backups --backup --prune 14
```

### Restore PostgreSQL From Snapshot
```bash
# 1. Stop API writers and workers first to quiesce connections
docker compose -f docker-compose.prod.yml stop backend worker-training worker-inference

# 2. Verify manifest checksum manually before restore
sha256sum /app/backups/nexora_pg_20261109_120000.dump
cat /app/backups/nexora_pg_20261109_120000.dump.manifest.json

# 3. Restore via pg_restore (--clean --if-exists --no-owner)
python backend/scripts/backup_db.py \
  --database-url "$DATABASE_URL" \
  --restore /app/backups/nexora_pg_20261109_120000.dump

# 4. Run pending migrations if any and restart services
docker compose -f docker-compose.prod.yml start backend worker-inference worker-training
```

### Create & Restore SQLite Backup (Single-Node Dev)
```bash
python backend/scripts/backup_db.py --backup --database-url "sqlite+aiosqlite:///./nexora.db" --backup-dir ./backups --prune 7
python backend/scripts/backup_db.py --restore ./backups/nexora_sqlite_YYYYMMDD_HHMMSS.db --target-sqlite ./nexora.db
```

---

## 4. Recommended RPO / RTO Targets & Storage Replication

| Environment | Recommended Cadence | Retention (`--prune`) | Off-Host Replication | Target RPO | Target RTO |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Development** | On-demand pre-migration | `7` snapshots | Local `./backups` | Manual | < 5 min |
| **Staging** | Daily cron (`02:00 UTC`) | `14` snapshots | Encrypted S3 bucket | 24 hours | < 15 min |
| **Production** | Every 6 hours + pre-deploy | `30` snapshots + WAL archiving (PITR on managed RDS/Cloud SQL) | Cross-region S3 / R2 with SSE-KMS | <= 15 min (with managed PITR) / 6 hours (logical) | < 30 min |

### Essential Disaster Recovery Checklist
- Store backup dumps and `.manifest.json` files outside container ephemeral disks (mounted `./backups` volume replicated off-host to S3/R2).
- Never store `.env.production` secrets unencrypted alongside database dumps.
- Schedule weekly automated restore drills in staging using `--verify-test` and periodic full `pg_restore` tests against an ephemeral Postgres container.
