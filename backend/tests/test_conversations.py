import pytest


@pytest.mark.asyncio
async def test_create_and_list_conversations(client, auth_headers):
    # 1. Create a conversation
    resp = await client.post(
        "/api/v1/conversations",
        headers=auth_headers,
        json={"title": "Test Chat 1", "model_id": "nexora-pro"}
    )
    assert resp.status_code == 201
    conv = resp.json()
    assert conv["title"] == "Test Chat 1"
    assert conv["model_id"] == "nexora-pro"
    conv_id = conv["id"]

    # 2. List conversations
    list_resp = await client.get("/api/v1/conversations", headers=auth_headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) >= 1
    assert any(c["id"] == conv_id for c in items)


@pytest.mark.asyncio
async def test_update_conversation_pin_and_archive(client, auth_headers):
    # Create conversation
    create_resp = await client.post(
        "/api/v1/conversations",
        headers=auth_headers,
        json={"title": "Original Title"}
    )
    conv_id = create_resp.json()["id"]

    # Rename
    patch_resp = await client.patch(
        f"/api/v1/conversations/{conv_id}",
        headers=auth_headers,
        json={"title": "Updated Title"}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Updated Title"

    # Toggle Pin
    pin_resp = await client.post(f"/api/v1/conversations/{conv_id}/pin", headers=auth_headers)
    assert pin_resp.status_code == 200
    assert pin_resp.json()["is_pinned"] is True

    # Toggle Archive
    archive_resp = await client.post(f"/api/v1/conversations/{conv_id}/archive", headers=auth_headers)
    assert archive_resp.status_code == 200
    assert archive_resp.json()["is_archived"] is True

    # Delete conversation
    del_resp = await client.delete(f"/api/v1/conversations/{conv_id}", headers=auth_headers)
    assert del_resp.status_code == 200

    # Ensure 404 after deletion
    get_resp = await client.get(f"/api/v1/conversations/{conv_id}", headers=auth_headers)
    assert get_resp.status_code == 404

