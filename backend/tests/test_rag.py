import pytest
from app.services.rag.rag_service import rag_service
from app.core.database import AsyncSessionLocal


@pytest.mark.asyncio
async def test_rag_chunking_and_ingestion():
    """Test text splitting into coherent chunks and document persistence."""
    sample_text = (
        "Quantum computing utilizes quantum mechanics such as superposition and entanglement.\n\n"
        "Grover's algorithm provides quadratic speedup for unstructured search problems.\n\n"
        "Shor's algorithm solves discrete logarithms and prime factorization in polynomial time."
    )

    chunks = rag_service.chunk_text(sample_text, chunk_size=120, chunk_overlap=30)
    assert len(chunks) >= 2
    assert any("Quantum" in c for c in chunks)

    async with AsyncSessionLocal() as session:
        col = await rag_service.create_collection(
            db=session,
            user_id="user_test_1",
            name="Quantum Algorithms",
            description="Reference material for quantum algorithms"
        )
        assert col.id is not None

        doc = await rag_service.ingest_document(
            db=session,
            collection_id=col.id,
            title="Quantum Foundations.md",
            content=sample_text,
            chunk_size=100,
            chunk_overlap=25
        )
        assert doc.id is not None
        assert doc.total_chunks >= 2


@pytest.mark.asyncio
async def test_rag_hybrid_search_and_citations():
    """Test hybrid search (dense + BM25Okapi) and citation generation."""
    async with AsyncSessionLocal() as session:
        col = await rag_service.create_collection(
            db=session,
            user_id="user_test_1",
            name="System Architecture",
        )
        await rag_service.ingest_document(
            db=session,
            collection_id=col.id,
            title="Distributed Transactions.md",
            content=(
                "Two-phase commit (2PC) ensures atomic distributed transactions across multiple shards.\n\n"
                "The coordinator sends prepare requests to all cohorts before initiating the commit phase."
            )
        )

        # Execute hybrid search
        results = await rag_service.hybrid_search(
            db=session,
            user_id="user_test_1",
            query="How does two-phase commit achieve atomic transactions?",
            top_k=2
        )

        assert len(results) >= 1
        top_match = results[0]
        assert "Two-phase commit" in top_match.content
        assert top_match.score > 0.0

        # Verify citation construction
        context_str, citations = rag_service.format_rag_context(results)
        assert "RETRIEVED KNOWLEDGE BASE CONTEXT" in context_str
        assert len(citations) >= 1
        assert citations[0].source_title == "Distributed Transactions.md"
        assert citations[0].chunk_index >= 1


@pytest.mark.asyncio
async def test_rag_tenant_isolation(client, auth_headers, auth_headers_user_2):
    """Test that User 2 cannot access or search User 1's knowledge collections."""
    # User 1 creates collection and document
    col_resp = await client.post(
        "/api/v1/rag/collections",
        headers=auth_headers,
        json={"name": "Proprietary Algorithm Secret"}
    )
    assert col_resp.status_code == 201
    col_id = col_resp.json()["id"]

    await client.post(
        f"/api/v1/rag/collections/{col_id}/documents",
        headers=auth_headers,
        json={
            "title": "Confidential Formula.txt",
            "content": "The proprietary formula coefficient is Alpha-Omega-9972."
        }
    )

    # User 2 performs hybrid search for the secret
    search_resp = await client.post(
        "/api/v1/rag/search",
        headers=auth_headers_user_2,
        json={"query": "What is the secret formula coefficient?"}
    )
    assert search_resp.status_code == 200
    results = search_resp.json()
    # Must be empty because User 2 has no access to User 1's collections
    assert len(results) == 0
