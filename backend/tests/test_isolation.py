import pytest


@pytest.mark.asyncio
async def test_tenant_data_isolation(client, auth_headers, auth_headers_user_2):
    # 1. User 1 creates conversation
    u1_conv = await client.post(
        "/api/v1/conversations",
        headers=auth_headers,
        json={"title": "User 1 Secret Conversation"}
    )
    assert u1_conv.status_code == 201
    u1_conv_id = u1_conv.json()["id"]

    # 2. User 1 sends a message
    u1_msg = await client.post(
        "/api/v1/messages",
        headers=auth_headers,
        json={"conversation_id": u1_conv_id, "content": "Sensitive Data from User 1"}
    )
    assert u1_msg.status_code == 200

    # 3. User 2 lists conversations -> MUST NOT see User 1's conversation
    u2_list = await client.get("/api/v1/conversations", headers=auth_headers_user_2)
    assert u2_list.status_code == 200
    u2_conv_ids = [c["id"] for c in u2_list.json()]
    assert u1_conv_id not in u2_conv_ids

    # 4. User 2 directly requests User 1's conversation -> MUST be 404 Not Found
    u2_get = await client.get(f"/api/v1/conversations/{u1_conv_id}", headers=auth_headers_user_2)
    assert u2_get.status_code == 404

    # 5. User 2 attempts to delete User 1's conversation -> MUST be 404 Not Found
    u2_del = await client.delete(f"/api/v1/conversations/{u1_conv_id}", headers=auth_headers_user_2)
    assert u2_del.status_code == 404

    # 6. Verify User 1's conversation is still intact
    u1_verify = await client.get(f"/api/v1/conversations/{u1_conv_id}", headers=auth_headers)
    assert u1_verify.status_code == 200
    assert u1_verify.json()["id"] == u1_conv_id

