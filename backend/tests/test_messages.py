import json
import pytest


@pytest.mark.asyncio
async def test_send_message_stream(client, auth_headers):
    # Send message to create conversation and stream response
    resp = await client.post(
        "/api/v1/messages",
        headers=auth_headers,
        json={
            "content": "Hello NEXORA! Tell me a fun fact.",
            "model": "nexora-pro",
            "reasoning_mode": True
        }
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    body = resp.text
    assert "data: " in body
    assert '"type": "start"' in body
    assert '"type": "token"' in body
    assert '"type": "done"' in body


@pytest.mark.asyncio
async def test_edit_message(client, auth_headers):
    # 1. Create conversation
    c_resp = await client.post(
        "/api/v1/conversations",
        headers=auth_headers,
        json={"title": "Chat to edit"}
    )
    conv_id = c_resp.json()["id"]

    # 2. Send message
    msg_resp = await client.post(
        "/api/v1/messages",
        headers=auth_headers,
        json={"conversation_id": conv_id, "content": "Original message text"}
    )
    assert msg_resp.status_code == 200

    # 3. Retrieve messages
    detail_resp = await client.get(f"/api/v1/conversations/{conv_id}", headers=auth_headers)
    messages = detail_resp.json()["messages"]
    user_msg = next(m for m in messages if m["role"] == "user")

    # 4. Edit message
    edit_resp = await client.put(
        f"/api/v1/messages/{user_msg['id']}",
        headers=auth_headers,
        json={"content": "Edited message text", "regenerate": False}
    )
    assert edit_resp.status_code == 200
    assert edit_resp.json()["content"] == "Edited message text"
    assert edit_resp.json()["is_edited"] is True


@pytest.mark.asyncio
async def test_message_feedback(client, auth_headers):
    # Create conversation and message
    c_resp = await client.post("/api/v1/conversations", headers=auth_headers, json={"title": "Feedback test"})
    conv_id = c_resp.json()["id"]
    await client.post("/api/v1/messages", headers=auth_headers, json={"conversation_id": conv_id, "content": "Ping"})

    detail_resp = await client.get(f"/api/v1/conversations/{conv_id}", headers=auth_headers)
    messages = detail_resp.json()["messages"]
    asst_msg = next(m for m in messages if m["role"] == "assistant")

    # Give like feedback
    fb_resp = await client.post(
        f"/api/v1/feedback/messages/{asst_msg['id']}",
        headers=auth_headers,
        json={"rating": "like", "comment": "Great structured response"}
    )
    assert fb_resp.status_code == 200
    assert fb_resp.json()["rating"] == "like"
    assert fb_resp.json()["comment"] == "Great structured response"
