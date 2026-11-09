import hashlib
import hmac
import json
import os
import time
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token
from app.models.ecosystem import SecurityEvent, SubscriptionPlan
from app.models.user import User
from app.services.agents.specialized_agents import BrowserAgent
from app.services.tools.sandbox import SSRFValidator
from tests.conftest import TestAsyncSessionLocal


@pytest.mark.asyncio
async def test_path_traversal_and_cross_tenant_file_isolation(
    client, auth_headers, auth_headers_user_2
):
    # 1. Path traversal attempt on Document Intelligence & Multimodal Vision
    res_doc = await client.post(
        "/api/v1/documents/parse",
        headers=auth_headers,
        json={"file_path": "../../.env"},
    )
    assert res_doc.status_code == 403

    res_img = await client.post(
        "/api/v1/multimodal/image/analyze",
        headers=auth_headers,
        json={"file_path": "../../backend/app/main.py"},
    )
    assert res_img.status_code == 403

    # 2. User 1 uploads a sensitive document; User 2 must be isolated from reading or parsing it
    up = await client.post(
        "/api/v1/attachments/upload",
        headers=auth_headers,
        files={"file": ("confidential.txt", b"NEXORA_SECRET_PAYLOAD_123", "text/plain")},
    )
    assert up.status_code == 201, up.text
    att_data = up.json()
    att_id = att_data["id"]

    try:
        dl_other = await client.get(f"/api/v1/attachments/{att_id}/download", headers=auth_headers_user_2)
        assert dl_other.status_code == 404

        parse_other_id = await client.post(
            "/api/v1/documents/parse",
            headers=auth_headers_user_2,
            json={"attachment_id": att_id},
        )
        assert parse_other_id.status_code == 404

        async with TestAsyncSessionLocal() as session:
            from app.models.attachment import Attachment
            att_row = await session.get(Attachment, att_id)
            assert att_row is not None
            storage_path = att_row.storage_path

        parse_other_path = await client.post(
            "/api/v1/documents/parse",
            headers=auth_headers_user_2,
            json={"file_path": storage_path},
        )
        assert parse_other_path.status_code == 403

        # Verify SecurityEvent forensic logging
        async with TestAsyncSessionLocal() as session:
            evts = (await session.execute(select(SecurityEvent))).scalars().all()
            evt_types = {e.event_type for e in evts}
            assert "path_traversal_blocked" in evt_types
            assert "unauthorized_file_access" in evt_types
            assert "tenant_file_isolation_blocked" in evt_types
    finally:
        # Clean up uploaded object
        async with TestAsyncSessionLocal() as session:
            from app.models.attachment import Attachment
            att_row = await session.get(Attachment, att_id)
            if att_row and os.path.exists(att_row.storage_path):
                os.remove(att_row.storage_path)


@pytest.mark.asyncio
async def test_upload_defense_svg_download_headers_and_plan_size_limit(
    client, auth_headers, admin_headers
):
    # 1. Forbidden dangerous extensions blocked (.exe, .html)
    for bad_name, content in [("malware.exe", b"MZ"), ("phish.html", b"<script>alert(1)</script>")]:
        bad_res = await client.post(
            "/api/v1/attachments/upload",
            headers=auth_headers,
            files={"file": (bad_name, content, "application/octet-stream")},
        )
        assert bad_res.status_code == 400

    # 2. Traversal filename sanitized to safe basename
    san_res = await client.post(
        "/api/v1/attachments/upload",
        headers=auth_headers,
        files={"file": ("../../evil_path/clean.txt", b"hello safe", "text/plain")},
    )
    assert san_res.status_code == 201
    assert san_res.json()["file_name"] == "clean.txt"
    san_id = san_res.json()["id"]

    # 3. SVG served strictly with attachment disposition + nosniff
    svg_res = await client.post(
        "/api/v1/attachments/upload",
        headers=auth_headers,
        files={"file": ("diagram.svg", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", "image/svg+xml")},
    )
    assert svg_res.status_code == 201
    svg_id = svg_res.json()["id"]

    dl_svg = await client.get(f"/api/v1/attachments/{svg_id}/download", headers=auth_headers)
    assert dl_svg.status_code == 200
    assert dl_svg.headers.get("x-content-type-options") == "nosniff"
    assert "attachment" in dl_svg.headers.get("content-disposition", "").lower()

    # 4. Plan max_file_size_mb enforcement (lower Free plan ceiling to 1 MB via Admin API)
    patch_free = await client.patch(
        "/api/v1/admin/plans/plan-free",
        headers=admin_headers,
        json={"max_file_size_mb": 1},
    )
    assert patch_free.status_code == 200

    oversize = await client.post(
        "/api/v1/attachments/upload",
        headers=auth_headers,
        files={"file": ("too_large.txt", b"A" * (1024 * 1024 + 64), "text/plain")},
    )
    assert oversize.status_code == 413

    # Clean up uploaded artifacts
    async with TestAsyncSessionLocal() as session:
        from app.models.attachment import Attachment
        for aid in (san_id, svg_id):
            row = await session.get(Attachment, aid)
            if row and os.path.exists(row.storage_path):
                os.remove(row.storage_path)


@pytest.mark.asyncio
async def test_sandbox_ast_blocking_and_ssrf_defense(client, auth_headers):
    # Python AST Sandbox blocking dangerous primitives
    for malicious in [
        "print(open('.env').read())",
        "import sys\nprint(sys.executable)",
        "import urllib.request\nurllib.request.urlopen('http://127.0.0.1:8000')",
    ]:
        sb = await client.post(
            "/api/v1/tools/sandbox/python",
            headers=auth_headers,
            json={"code": malicious},
        )
        assert sb.status_code == 200
        body = sb.json()
        assert body["success"] is False
        assert "Security Policy Violation" in (body["result"].get("error") or "")

    # SSRF Validator checks
    for bad_url in [
        "http://169.254.169.254/latest/meta-data/",
        "http://2130706433/",
        "http://user:pass@127.0.0.1:8000/",
        "http://metadata.internal.corp/secrets",
        "file:///etc/passwd",
    ]:
        ok, _ = SSRFValidator.validate_url(bad_url)
        assert ok is False, f"SSRF URL should have been blocked: {bad_url}"

    ok_pub, _ = SSRFValidator.validate_url("https://en.wikipedia.org/wiki/Artificial_intelligence")
    assert ok_pub is True

    # BrowserAgent defense against metadata endpoint
    agent = BrowserAgent()
    step = await agent.process("inspect metadata", {"url": "http://169.254.169.254/latest/meta-data/"})
    assert step.status == "blocked"
    assert "blocked" in step.output.lower()


@pytest.mark.asyncio
async def test_rbac_api_key_revocation_and_plan_model_gates(client, auth_headers, admin_headers, test_user_2):
    # 1. Unauthenticated access rejected with 401
    for path in [
        "/api/v1/admin/overview",
        "/api/v1/lab/models",
        "/v1/models",
    ]:
        r = await client.get(path)
        assert r.status_code == 401
    assert (await client.post("/v1/chat/completions", json={"model": "nexora-fast", "messages": [{"role": "user", "content": "hi"}]})).status_code == 401
    assert (await client.post("/v1/embeddings", json={"input": "hello"})).status_code == 401

    # 2. Standard user denied Admin & Model Lab with 403
    for path in ["/api/v1/admin/overview", "/api/v1/admin/users", "/api/v1/admin/security-events", "/api/v1/lab/models", "/api/v1/lab/jobs", "/api/v1/lab/deployments"]:
        r = await client.get(path, headers=auth_headers)
        assert r.status_code == 403, f"Expected 403 on {path}, got {r.status_code}"

    # 3. Promote test_user_2 -> researcher: allowed on Lab, denied on Admin
    promo = await client.patch(
        f"/api/v1/admin/users/{test_user_2.id}",
        headers=admin_headers,
        json={"role": "researcher"},
    )
    assert promo.status_code == 200
    researcher_headers = {"Authorization": f"Bearer {create_access_token(test_user_2.id)}"}
    assert (await client.get("/api/v1/lab/models", headers=researcher_headers)).status_code == 200
    assert (await client.get("/api/v1/admin/overview", headers=researcher_headers)).status_code == 403

    # 4. Free tier denied developer API keys (403) and Pro-only model "gpt-4o" (403)
    free_key_res = await client.post("/api/v1/developer/keys", headers=auth_headers, json={"name": "Blocked Free Key"})
    assert free_key_res.status_code == 403

    free_gpt4o = await client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Test"}]},
    )
    assert free_gpt4o.status_code == 403

    # 5. Revoked Developer API key rejected with 401
    up = await client.post("/api/v1/billing/subscribe", headers=auth_headers, json={"tier": "pro", "billing_cycle": "monthly"})
    assert up.status_code == 200

    key_create = await client.post("/api/v1/developer/keys", headers=auth_headers, json={"name": "Audit Key"})
    assert key_create.status_code == 201
    key_id = key_create.json()["id"]
    raw_key = key_create.json()["plaintext_key"]

    assert (await client.get("/v1/models", headers={"Authorization": f"Bearer {raw_key}"})).status_code == 200
    rev = await client.post(f"/api/v1/developer/keys/{key_id}/revoke", headers=auth_headers)
    assert rev.status_code == 200
    assert (await client.get("/v1/models", headers={"Authorization": f"Bearer {raw_key}"})).status_code == 401


@pytest.mark.asyncio
async def test_stripe_webhook_hmac_verification_and_headers_gdpr_erasure(client, auth_headers):
    payload_bytes = json.dumps({"id": "evt_test_1", "type": "invoice.paid"}).encode("utf-8")

    # 1. Missing signature rejected (400)
    missing_sig = await client.post("/api/v1/billing/webhook", content=payload_bytes)
    assert missing_sig.status_code == 400

    # 2. Invalid signature rejected (400)
    bad_sig = await client.post(
        "/api/v1/billing/webhook",
        content=payload_bytes,
        headers={"Stripe-Signature": "t=1700000000,v1=deadbeef"},
    )
    assert bad_sig.status_code == 400

    # 3. Valid HMAC-SHA256 signature accepted (200)
    ts = str(int(time.time()))
    secret = settings.STRIPE_WEBHOOK_SECRET or "whsec_nexora_local_test"
    signed = f"{ts}.".encode("utf-8") + payload_bytes
    sig = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    good_sig = await client.post(
        "/api/v1/billing/webhook",
        content=payload_bytes,
        headers={"Stripe-Signature": f"t={ts},v1={sig}"},
    )
    assert good_sig.status_code == 200
    assert good_sig.json()["received"] is True

    # 4. Security response headers on /health & no reset token leak
    h = await client.get("/health")
    assert h.status_code == 200
    assert h.headers.get("x-content-type-options") == "nosniff"
    assert h.headers.get("x-frame-options") == "DENY"

    rst = await client.post("/api/v1/auth/password-reset-request", json={"email": "test@nexora.ai"})
    assert rst.status_code == 200
    assert "token" not in rst.text.lower().replace("reset link", "")

    # 5. GDPR Right-to-Erasure removes user and physical disk upload
    up = await client.post(
        "/api/v1/attachments/upload",
        headers=auth_headers,
        files={"file": ("gdpr_temp.txt", b"personal data", "text/plain")},
    )
    assert up.status_code == 201
    att_id = up.json()["id"]
    async with TestAsyncSessionLocal() as session:
        from app.models.attachment import Attachment
        storage_path = (await session.get(Attachment, att_id)).storage_path
    assert os.path.exists(storage_path)

    del_res = await client.delete("/api/v1/users/me", headers=auth_headers)
    assert del_res.status_code == 200
    assert not os.path.exists(storage_path)
    assert (await client.get("/api/v1/users/me", headers=auth_headers)).status_code == 401


@pytest.mark.asyncio
async def test_truthful_gateway_fallback_attribution(client, auth_headers):
    # Upgrade to Pro so user is permitted to request "gpt-4o"
    sub = await client.post("/api/v1/billing/subscribe", headers=auth_headers, json={"tier": "pro", "billing_cycle": "monthly"})
    assert sub.status_code == 200

    # Request OpenAI "gpt-4o" when OPENAI_API_KEY is unset -> must truthfully disclose fallback to nexora
    from app.services.llm.gateway import gateway

    orig_key = settings.OPENAI_API_KEY
    openai_provider = gateway.get_provider("openai")
    orig_explicit_key = openai_provider._explicit_api_key
    settings.OPENAI_API_KEY = ""
    openai_provider._explicit_api_key = None
    try:
        # 1. OpenAI-compatible JSON completion fallback attribution
        res = await client.post(
            "/v1/chat/completions",
            headers=auth_headers,
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Explain neural scaling laws briefly."}],
                "max_tokens": 32,
            },
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["model"] == "nexora-flagship"
        assert data["nexora_attribution"]["requested_model"] == "gpt-4o"
        assert data["nexora_attribution"]["resolved_model"] == "nexora-flagship"
        assert data["nexora_attribution"]["actual_provider"] == "nexora"
        assert data["nexora_attribution"]["fallback_used"] is True
        assert data["nexora_attribution"]["fallback_from_model"] == "gpt-4o"

        # 2. Chat SSE streaming (/api/v1/messages) truthful fallback attribution
        sse_res = await client.post(
            "/api/v1/messages",
            headers=auth_headers,
            json={
                "content": "Summarize attention scaling in one sentence.",
                "model": "gpt-4o",
                "reasoning_mode": False,
            },
        )
        assert sse_res.status_code == 200, sse_res.text
        events = []
        for line in sse_res.text.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:].strip()))
        done_events = [ev for ev in events if ev.get("type") == "done"]
        assert len(done_events) == 1
        assert done_events[0]["resolved_model"] == "nexora-flagship"
        assert done_events[0]["actual_provider"] == "nexora"
        assert done_events[0]["fallback_used"] is True
        assert done_events[0]["fallback_from_model"] == "gpt-4o"
    finally:
        settings.OPENAI_API_KEY = orig_key
        openai_provider._explicit_api_key = orig_explicit_key
