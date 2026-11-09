import os
import shutil
import pytest

from app.services.model_registry.registry import model_registry


@pytest.mark.asyncio
async def test_commercial_billing_developer_api_and_usage_accounting_e2e(client):
    # 1. Register fresh commercial customer
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "founder@acme-ai.io",
            "username": "acme_founder",
            "password": "StrongCommercialPassword99!",
            "display_name": "Acme Founder",
        },
    )
    assert reg.status_code == 201, reg.text
    jwt_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    # 2. Verify initial Free tier & model permissions
    plans_res = await client.get("/api/v1/billing/plans")
    assert plans_res.status_code == 200
    assert {p["tier"] for p in plans_res.json()} >= {"free", "pro", "enterprise"}

    sub_res = await client.get("/api/v1/billing/subscription", headers=jwt_headers)
    assert sub_res.status_code == 200
    assert sub_res.json()["plan"]["tier"] == "free"
    assert sub_res.json()["plan"]["api_access_enabled"] is False

    models_free = {m["id"]: m for m in (await client.get("/api/v1/models", headers=jwt_headers)).json()}
    assert models_free["nexora-flagship"]["plan_permitted"] is True
    assert models_free["gpt-4o"]["plan_permitted"] is False

    # 3. Upgrade to Pro (monthly) & inspect persisted invoice
    up_res = await client.post(
        "/api/v1/billing/subscribe",
        headers=jwt_headers,
        json={"tier": "pro", "billing_cycle": "monthly", "payment_method_summary": "Visa ****4242"},
    )
    assert up_res.status_code == 200, up_res.text
    assert up_res.json()["plan"]["tier"] == "pro"
    assert up_res.json()["invoice"]["amount_usd"] > 0

    inv_res = await client.get("/api/v1/billing/invoices", headers=jwt_headers)
    assert inv_res.status_code == 200
    assert len(inv_res.json()) >= 1
    assert inv_res.json()[0]["status"] == "paid"

    # 4. Create Developer API Key -> plaintext exposed ONCE, masked on list
    key_create = await client.post(
        "/api/v1/developer/keys",
        headers=jwt_headers,
        json={"name": "Production Backend Key", "scopes": ["models", "chat", "embeddings"], "expires_in_days": 90},
    )
    assert key_create.status_code == 201, key_create.text
    key_data = key_create.json()
    key_id = key_data["id"]
    raw_key = key_data["plaintext_key"]
    assert raw_key.startswith("nex_live_")

    keys_list = await client.get("/api/v1/developer/keys", headers=jwt_headers)
    assert keys_list.status_code == 200
    assert len(keys_list.json()) == 1
    assert "plaintext_key" not in keys_list.json()[0]
    assert "key_hash" not in keys_list.json()[0]
    assert raw_key not in keys_list.text

    api_headers = {"Authorization": f"Bearer {raw_key}"}

    # 5. Execute real OpenAI-compatible SDK endpoints (/v1/models, /v1/embeddings, /v1/chat/completions, /v1/completions)
    v1_models = await client.get("/v1/models", headers=api_headers)
    assert v1_models.status_code == 200
    assert any(m["id"] == "nexora-flagship" for m in v1_models.json()["data"])

    emb = await client.post(
        "/v1/embeddings",
        headers=api_headers,
        json={"model": "text-embedding-3-small", "input": ["NEXORA enterprise embeddings", "Commercial RAG"]},
    )
    assert emb.status_code == 200, emb.text
    assert len(emb.json()["data"]) == 2
    assert len(emb.json()["data"][0]["embedding"]) > 10

    chat = await client.post(
        "/v1/chat/completions",
        headers=api_headers,
        json={
            "model": "nexora-flagship",
            "messages": [{"role": "user", "content": "Give one concise sentence about Transformer attention."}],
            "max_tokens": 32,
        },
    )
    assert chat.status_code == 200, chat.text
    assert chat.json()["object"] == "chat.completion"
    assert chat.json()["usage"]["total_tokens"] > 0
    assert chat.json()["nexora_attribution"]["actual_provider"] == "nexora"
    assert chat.json()["nexora_attribution"]["fallback_used"] is False

    cmpl = await client.post(
        "/v1/completions",
        headers=api_headers,
        json={"model": "nexora-fast", "prompt": "Define attention entropy:", "max_tokens": 24},
    )
    assert cmpl.status_code == 200
    assert cmpl.json()["object"] == "text_completion"

    # 6. Verify usage & billing accounting updated
    usage_res = await client.get("/api/v1/developer/usage", headers=jwt_headers)
    assert usage_res.status_code == 200
    usage = usage_res.json()
    assert usage["summary"]["total_requests"] >= 3
    assert usage["summary"]["total_tokens"] > 0
    assert usage["tokens_used_period"] > 0
    assert len(usage["recent_logs"]) >= 3

    # 7. Key Rotation invalidates old key immediately and activates replacement key
    rot = await client.post(f"/api/v1/developer/keys/{key_id}/rotate", headers=jwt_headers)
    assert rot.status_code == 200
    rotated_id = rot.json()["id"]
    new_raw_key = rot.json()["plaintext_key"]
    assert new_raw_key != raw_key

    assert (await client.get("/v1/models", headers=api_headers)).status_code == 401
    assert (await client.get("/v1/models", headers={"X-API-Key": new_raw_key})).status_code == 200

    # Revoke rotated key and schedule then immediately cancel subscription
    assert (await client.post(f"/api/v1/developer/keys/{rotated_id}/revoke", headers=jwt_headers)).status_code == 200
    assert (await client.post("/api/v1/billing/cancel", headers=jwt_headers, json={"immediate": False})).json()["cancel_at_period_end"] is True
    assert (await client.post("/api/v1/billing/cancel", headers=jwt_headers, json={"immediate": True})).json()["tier"] == "free"


@pytest.mark.asyncio
async def test_admin_control_center_and_lab_checkpoint_publish_bridge_e2e(
    client, admin_headers, test_user
):
    published_model_id = "nexora-e2e-proprietary-v1"
    created_ckpt_files = []
    try:
        # 1. Admin telemetry & management surfaces
        for path in [
            "/api/v1/admin/overview",
            "/api/v1/admin/users",
            "/api/v1/admin/plans",
            "/api/v1/admin/models",
            "/api/v1/admin/providers",
            "/api/v1/admin/analytics",
            "/api/v1/admin/training-and-gpu",
            "/api/v1/admin/agent-activity",
            "/api/v1/admin/security-events",
            "/api/v1/admin/audit-logs",
            "/api/v1/admin/system-health",
        ]:
            r = await client.get(path, headers=admin_headers)
            assert r.status_code == 200, f"Admin route {path} failed: {r.text}"

        # Ensure /admin/providers masks secrets safely
        prov = (await client.get("/api/v1/admin/providers", headers=admin_headers)).json()
        assert "credential_status" in prov
        assert prov["credential_status"]["nexora_proprietary"] is True

        # Admin modifies user role & plan + updates plan configuration
        u_patch = await client.patch(
            f"/api/v1/admin/users/{test_user.id}",
            headers=admin_headers,
            json={"role": "researcher", "plan_tier": "pro"},
        )
        assert u_patch.status_code == 200
        assert u_patch.json()["role"] == "researcher"

        p_patch = await client.patch(
            "/api/v1/admin/plans/plan-pro",
            headers=admin_headers,
            json={"rate_limit_rpm": 150},
        )
        assert p_patch.status_code == 200
        assert p_patch.json()["rate_limit_rpm"] == 150

        # 2. Lab-to-Production Checkpoint Bridge: run fast Lab experiment -> validate & publish -> serve
        exp_create = await client.post(
            "/api/v1/lab/experiments",
            headers=admin_headers,
            json={
                "name": "E2E Proprietary Checkpoint Promotion",
                "model_name": "NEXORA-Nano-Bridge",
                "hyperparameters": {"max_steps": 4, "learning_rate": 1e-3, "batch_size": 2, "seed": 7},
            },
        )
        assert exp_create.status_code == 201, exp_create.text
        exp_id = exp_create.json()["id"]

        exp_run = await client.post(f"/api/v1/lab/experiments/{exp_id}/start", headers=admin_headers)
        assert exp_run.status_code == 200, exp_run.text
        exp_detail = await client.get(f"/api/v1/lab/experiments/{exp_id}", headers=admin_headers)
        assert exp_detail.status_code == 200, exp_detail.text
        ckpts = exp_detail.json()["checkpoints"]
        assert len(ckpts) >= 1
        ckpt_id = ckpts[-1]["id"]
        created_ckpt_files.extend([c["storage_path"] for c in ckpts if c.get("storage_path")])

        # Publish validated checkpoint via Admin bridge
        pub = await client.post(
            "/api/v1/admin/models/publish-checkpoint",
            headers=admin_headers,
            json={
                "checkpoint_id": ckpt_id,
                "model_id": published_model_id,
                "display_name": "NEXORA E2E Proprietary v1",
                "description": "Validated Model Lab checkpoint promoted into commercial production.",
                "min_plan_tier": "free",
                "input_price_per_million": 0.40,
                "output_price_per_million": 1.20,
            },
        )
        assert pub.status_code == 201, pub.text
        assert pub.json()["id"] == published_model_id
        assert pub.json()["is_proprietary"] is True

        # Confirm published model is dynamically visible in both /api/v1/models and /v1/models
        cat_models = {m["id"]: m for m in (await client.get("/api/v1/models", headers=admin_headers)).json()}
        assert published_model_id in cat_models
        assert cat_models[published_model_id]["is_proprietary"] is True

        v1_models = {m["id"]: m for m in (await client.get("/v1/models", headers=admin_headers)).json()["data"]}
        assert published_model_id in v1_models
        assert v1_models[published_model_id]["proprietary"] is True

        # Run inference through OpenAI-compatible gateway against newly published proprietary model
        inf = await client.post(
            "/v1/chat/completions",
            headers=admin_headers,
            json={
                "model": published_model_id,
                "messages": [{"role": "user", "content": "Respond with a concise architectural greeting."}],
                "max_tokens": 24,
            },
        )
        assert inf.status_code == 200, inf.text
        assert inf.json()["model"] == published_model_id
        assert inf.json()["nexora_attribution"]["actual_provider"] == "nexora"
        assert inf.json()["nexora_attribution"]["fallback_used"] is False

        # Toggle disable & verify hidden from active catalog
        m_dis = await client.patch(
            f"/api/v1/admin/models/{published_model_id}",
            headers=admin_headers,
            json={"is_enabled": False},
        )
        assert m_dis.status_code == 200
        assert m_dis.json()["is_enabled"] is False
        cat_after = {m["id"] for m in (await client.get("/api/v1/models", headers=admin_headers)).json()}
        assert published_model_id not in cat_after

        # 3. Verify Prometheus observability /metrics endpoint
        metrics = await client.get("/metrics")
        assert metrics.status_code == 200
        assert "nexora_http_requests_total" in metrics.text
        assert "nexora_models_registered" in metrics.text
    finally:
        model_registry._models.pop(published_model_id, None)
        parent_dirs = set()
        for fpath in created_ckpt_files:
            if fpath and os.path.exists(fpath):
                parent_dirs.add(os.path.dirname(fpath))
                if os.path.isdir(fpath):
                    shutil.rmtree(fpath, ignore_errors=True)
                else:
                    os.remove(fpath)
        for pdir in parent_dirs:
            if pdir and os.path.isdir(pdir) and not os.listdir(pdir):
                os.rmdir(pdir)
