import pytest
from app.services.memory.memory_service import memory_service
from app.core.database import AsyncSessionLocal


@pytest.mark.asyncio
async def test_memory_store_and_retrieve():
    """Test storing a memory and retrieving it via semantic similarity."""
    async with AsyncSessionLocal() as session:
        # Store technical preference
        mem = await memory_service.store_memory(
            db=session,
            user_id="user_test_1",
            content="User prefers TypeScript with strict typing and Next.js App Router",
            memory_type="user_preference",
            category="preference"
        )
        assert mem.id is not None
        assert mem.content == "User prefers TypeScript with strict typing and Next.js App Router"

        # Retrieve relevant memories
        results = await memory_service.retrieve_relevant_memories(
            db=session,
            user_id="user_test_1",
            query="What is the user's preferred frontend framework and TypeScript setup?",
            top_k=3,
            min_similarity=0.10
        )
        assert len(results) >= 1
        assert "TypeScript" in results[0].content
        assert results[0].similarity > 0.0


@pytest.mark.asyncio
async def test_memory_duplicate_detection():
    """Test duplicate detection: storing near-identical memory updates existing instead of inserting duplicate."""
    async with AsyncSessionLocal() as session:
        mem1 = await memory_service.store_memory(
            db=session,
            user_id="user_test_1",
            content="User prefers PostgreSQL over MySQL for all database projects",
            memory_type="user_preference",
            category="preference"
        )

        # Store near-identical statement
        mem2 = await memory_service.store_memory(
            db=session,
            user_id="user_test_1",
            content="User prefers PostgreSQL over MySQL for all database projects",
            memory_type="user_preference",
            category="preference"
        )

        # Must have the same ID because duplicate detection updated the existing record
        assert mem1.id == mem2.id

        # Verify only 1 memory exists in db for this category
        all_mems = await memory_service.list_memories(db=session, user_id="user_test_1", category="preference")
        matching = [m for m in all_mems if "PostgreSQL" in m.content]
        assert len(matching) == 1


@pytest.mark.asyncio
async def test_memory_tenant_isolation(client, auth_headers, auth_headers_user_2):
    """Test strict tenant isolation: User 2 cannot access or delete User 1's memory."""
    # 1. User 1 creates memory via API
    resp1 = await client.post(
        "/api/v1/memories",
        headers=auth_headers,
        json={"content": "Confidential User 1 project secret API key", "category": "fact"}
    )
    assert resp1.status_code == 201
    mem_id = resp1.json()["id"]

    # 2. User 2 lists memories -> must NOT see User 1's memory
    list_resp = await client.get("/api/v1/memories", headers=auth_headers_user_2)
    assert list_resp.status_code == 200
    user2_mem_ids = [m["id"] for m in list_resp.json()]
    assert mem_id not in user2_mem_ids

    # 3. User 2 attempts to delete User 1's memory -> must return 404
    del_resp = await client.delete(f"/api/v1/memories/{mem_id}", headers=auth_headers_user_2)
    assert del_resp.status_code == 404

    # 4. User 1 can delete own memory
    del_ok = await client.delete(f"/api/v1/memories/{mem_id}", headers=auth_headers)
    assert del_ok.status_code == 200
