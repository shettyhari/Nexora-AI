# NEXORA AI – Comprehensive Security Audit & Verification Report

**Version:** 2.0.0  
**Audit Date:** 2026-11-09  
**Verification Suite:** [`backend/tests/test_security_audit.py`](backend/tests/test_security_audit.py) (6/6 integration security tests passed) + [`backend/tests/test_sandbox.py`](backend/tests/test_sandbox.py) (8/8 passed) + [`backend/tests/test_isolation.py`](backend/tests/test_isolation.py) (1/1 passed)  

---

## 1. Executive Summary

A full-stack security audit was conducted across NEXORA AI's authentication, API key management, file uploads/downloads, document/multimodal parsers, Python execution sandbox, web research SSRF guards, billing webhooks, RBAC access boundaries, gateway model attribution, HTTP security headers, and GDPR compliance flows.

All identified vulnerabilities and edge-case failure modes were remediated and locked behind automated security regression tests inside the **91-test backend suite**.

---

## 2. Attack Surface Matrix & Verified Controls

| Security Domain | Controls Implemented | Source Module(s) | Automated Verification |
| :--- | :--- | :--- | :--- |
| **Path Traversal Confinement** | Null-byte & `..` segment rejection; `os.path.realpath` + `os.path.commonpath` prefix verification strictly inside `UPLOAD_DIR`; forensic `SecurityEvent` persisted cleanly before HTTP 403/404. | [`security_guards.py`](backend/app/core/security_guards.py) (`resolve_safe_file_path`, `is_path_within_base`) | `test_path_traversal_and_cross_tenant_file_isolation` (`../../.env`, `../../backend/app/main.py`) |
| **Cross-Tenant Ownership Isolation** | Attachment lookup scoped by `Attachment.user_id == current_user.id`; direct `file_path` reads cross-checked against owning `Attachment` row; RAG, memories, and conversations strictly tenant-scoped. | [`security_guards.py`](backend/app/core/security_guards.py), [`attachments.py`](backend/app/api/v1/attachments.py), [`deps.py`](backend/app/api/deps.py) | `test_path_traversal_and_cross_tenant_file_isolation`, `test_tenant_data_isolation`, `test_rag_tenant_isolation`, `test_memory_tenant_isolation` |
| **File Upload & Download Defense** | Traversal basename stripping (`sanitize_filename`); dangerous active extension denylist (`FORBIDDEN_UPLOAD_EXTENSIONS`: `.exe`, `.dll`, `.bat`, `.ps1`, `.sh`, `.php`, `.html`, `.htm`, etc.) + strict allowlist; per-plan `max_file_size_mb` cap (`413 Payload Too Large`); `X-Content-Type-Options: nosniff` + `Content-Disposition: attachment` on `.svg`/scriptable files. | [`security_guards.py`](backend/app/core/security_guards.py), [`attachments.py`](backend/app/api/v1/attachments.py) | `test_upload_defense_svg_download_headers_and_plan_size_limit` |
| **Python Sandbox AST Isolation** | `CodeASTAnalyzer` AST pre-execution scan blocks dangerous modules (`os`, `sys`, `subprocess`, `socket`, `ctypes`, `importlib`, `pickle`, `urllib`, `http`, `requests`, `httpx`), calls (`open`, `eval`, `exec`, `__import__`, `getattr`), and dunder attributes (`__subclasses__`, `__globals__`, `__builtins__`); executes safely in isolated subprocess with timeout. | [`sandbox.py`](backend/app/services/tools/sandbox.py) (`CodeASTAnalyzer`), [`tools.py`](backend/app/api/v1/tools.py) | `test_sandbox_ast_blocking_and_ssrf_defense`, `test_sandbox.py` (8 tests) |
| **SSRF Perimeter Protection** | `SSRFValidator.validate_url()` enforces `http`/`https` only, rejects embedded `user:pass@` URL credentials, blocks internal hostnames (`.local`, `.internal`, `.localhost`, `metadata.google.internal`, `169.254.169.254`), decodes decimal/hex IP obfuscations (`http://2130706433/`), and blocks RFC1918/loopback/link-local/CGNAT IPv4 & IPv6 CIDRs. | [`sandbox.py`](backend/app/services/tools/sandbox.py) (`SSRFValidator`), [`specialized_agents.py`](backend/app/services/agents/specialized_agents.py) (`BrowserAgent`) | `test_sandbox_ast_blocking_and_ssrf_defense`, `test_ssrf_blocking_on_scrape`, `test_ssrf_validator_blocks_private_ips` |
| **RBAC & Service Separation** | Strict three-tier role enforcement: `user` (commercial app), `researcher` (Model Lab access via `require_lab_access`), `admin` (Control Center via `require_admin`); Lab & Admin routes fail closed with `401` (unauthenticated) / `403` (unauthorized) and record `SecurityEvent` telemetry. | [`deps.py`](backend/app/api/deps.py), [`admin.py`](backend/app/api/v1/admin.py), [`lab.py`](backend/app/api/v1/lab.py), [`inference.py`](backend/app/api/v1/inference.py) | `test_rbac_api_key_revocation_and_plan_model_gates` |
| **Commercial API Key Cryptographic Lifecycle** | Keys use `secrets.token_urlsafe(32)` (`nex_live_...`), plaintext shown ONCE on minting; only `hash_api_key()` (`SHA-256`) stored in `DeveloperApiKey.key_hash`; plan entitlement (`api_access_enabled`) enforced on `/developer/keys` and `/v1/*`; immediate invalidation on `revoke` or atomic `rotate`. | [`developer.py`](backend/app/api/v1/developer.py), [`deps.py`](backend/app/api/deps.py) (`authenticate_api_principal`) | `test_rbac_api_key_revocation_and_plan_model_gates`, `test_commercial_billing_developer_api_and_usage_accounting_e2e` |
| **Rate Limiting & Brute-Force Protection** | `SlidingWindowRateLimiter` uses atomic Redis `INCR` + `EXPIRE` counters (with `asyncio.Lock` in-memory fallback); per-IP auth limits on `/auth/register` & `/auth/login`; per-plan RPM + monthly token quota enforcement; nginx zone defense (`30r/m` auth, `120r/m` API). | [`rate_limiter.py`](backend/app/core/rate_limiter.py), [`auth.py`](backend/app/api/v1/auth.py), [`billing_service.py`](backend/app/services/billing_service.py), [`nginx.conf`](infra/nginx.conf) | `test_commercial_billing_developer_api_and_usage_accounting_e2e` |
| **Payment Webhook Integrity** | Stripe webhook handler computes HMAC-SHA256 over signed `{timestamp}.{raw_body}` and compares in constant time (`hmac.compare_digest`); invalid/missing `Stripe-Signature` logs `SecurityEvent(event_type="invalid_webhook_signature", severity="high")` and returns `400`. | [`billing.py`](backend/app/api/v1/billing.py), [`billing_service.py`](backend/app/services/billing_service.py) | `test_stripe_webhook_hmac_verification_and_headers_gdpr_erasure` |
| **HTTP Security Headers & Secret Hygiene** | Middleware sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`, and `Strict-Transport-Security` (in production); `validate_production_secrets()` halts boot on weak/default `SECRET_KEY`; password reset never returns or logs tokens; `/admin/providers` returns booleans only. | [`main.py`](backend/app/main.py), [`config.py`](backend/app/core/config.py), [`auth.py`](backend/app/api/v1/auth.py), [`admin.py`](backend/app/api/v1/admin.py) | `test_stripe_webhook_hmac_verification_and_headers_gdpr_erasure`, `test_admin_control_center_and_lab_checkpoint_publish_bridge_e2e` |
| **Truthful Model Attribution** | `UnifiedModelGateway` never silently serves local fallback under an external provider/model alias; unwraps `(str, Enum)` provider keys explicitly, reads runtime `settings` dynamically, and surfaces `resolved_model`, `actual_provider`, `fallback_used`, and `fallback_from_model` across SSE and `/v1/chat/completions`. | [`gateway.py`](backend/app/services/llm/gateway.py), [`messages.py`](backend/app/api/v1/messages.py), [`inference.py`](backend/app/api/v1/inference.py) | `test_truthful_gateway_fallback_attribution` |
| **GDPR Right-to-Erasure (`DELETE /api/v1/users/me`)** | Deletes physical uploaded objects via `object_storage.delete_object()`, purges cross-table user records (`Attachment`, `Feedback`, `Memory`, `KnowledgeCollection`, `AgentWorkflow`, `ToolExecution`, `MediaJob`, `DeveloperApiKey`, `BillingInvoice`, `UserSubscription`, `User`), emits anonymized `AuditLog` (`user_id=None`), and invalidates tokens cleanly. | [`users.py`](backend/app/api/v1/users.py) | `test_stripe_webhook_hmac_verification_and_headers_gdpr_erasure` |

---

## 3. Audit Remediations Applied During Prompt 6 Hardening

During final audit verification, the following subtle issues were uncovered and fixed:

1. **Python 3.12 `(str, Enum)` Gateway Lookup Vulnerability / Attribution Defect (`gateway.py`):**
   - *Finding:* On Python 3.12, `str(ModelProvider.OPENAI).lower()` evaluated to `"modelprovider.openai"` instead of `"openai"`. `UnifiedModelGateway.get_provider()` missed `self._providers` and defaulted to `NexoraProvider` while external providers also cached `api_key` only at class instantiation. Because `NexoraProvider.is_configured()` returned `True`, unconfigured external requests bypassed fallback disclosure (`fallback_used=False`).
   - *Fix:* Normalized provider registry keys using `ModelProvider.value` and unwrapped `Enum.value` inside `get_provider()`, plus converted `OpenAIProvider`, `GeminiProvider`, `AnthropicProvider`, `HuggingFaceProvider`, and `OpenAICompatibleProvider` to dynamic `@property` runtime settings resolution.
2. **Checkpoint Integrity SHA-256 Digest Mismatch (`lab/experiments/runner.py`):**
   - *Finding:* `TrainingRunner` previously hashed full `weights_bytes` but sliced `weights_bytes[:1024]` when writing the `.bin` checkpoint to disk, causing `CheckpointManager.validate_checkpoint()` SHA-256 checks to fail during production publication.
   - *Fix:* Updated `TrainingRunner` to persist full `weights_bytes` matching `weights_sha256`.
3. **Forensic `SecurityEvent` Persistence Across Error Paths (`security_guards.py`, `deps.py`, `attachments.py`, `billing.py`):**
   - *Finding:* FastAPI exception rollbacks would discard uncommitted forensic `SecurityEvent` rows recorded immediately before raising `HTTPException(400/401/403/404)`.
   - *Fix:* Explicit `await db.commit()` immediately after `record_security_event()` ensures forensic attack records survive HTTP error responses for `/api/v1/admin/security-events`.
4. **Admin Storage & Hardware Telemetry Consistency (`object_storage.py`, `admin.py`):**
   - *Finding:* Aligned telemetry payload keys (`ram_used_pct` and `storage.status`) between backend responses and `/admin` frontend TypeScript contracts.

---

## 4. Production Hardening Sign-Off Requirements

Before deploying live commercial traffic:
- Set `ENVIRONMENT=production` and `STRICT_SECRET_VALIDATION=true` with a unique `>= 32`-char `SECRET_KEY` (`openssl rand -hex 32`).
- Restrict public edge ports strictly to TLS-terminated Nginx (`443`/`80`); keep `postgres`, `redis`, `worker-training`, and `worker-inference` exclusively on the internal `nexora_internal` network.
- Configure `STORAGE_BACKEND=s3` with encrypted buckets and enable managed PostgreSQL PITR alongside `backend/scripts/backup_db.py --prune`.
