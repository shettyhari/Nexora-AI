import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel
from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.rag import DocumentChunk, KnowledgeCollection, KnowledgeDocument
from app.services.embedding.embedding_service import embedding_service

logger = logging.getLogger(__name__)


class Citation(BaseModel):
    id: int
    document_id: str
    source_title: str
    chunk_index: int
    content_snippet: str


class ChunkSearchResult(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    collection_id: str
    chunk_index: int
    content: str
    score: float
    dense_score: float = 0.0
    sparse_score: float = 0.0


class RAGService:
    """Enterprise RAG Engine providing document ingestion, hybrid BM25/vector search, and citations."""

    def chunk_text(self, text: str, chunk_size: int = 800, chunk_overlap: int = 150) -> List[str]:
        """Recursive character chunking respecting paragraph and sentence boundaries."""
        clean_text = text.replace("\r\n", "\n").strip()
        if not clean_text:
            return []

        if len(clean_text) <= chunk_size:
            return [clean_text]

        chunks = []
        start = 0
        text_len = len(clean_text)

        while start < text_len:
            end = min(start + chunk_size, text_len)
            if end < text_len:
                # Find optimal break point: paragraph -> newline -> sentence -> space
                break_point = -1
                for sep in ["\n\n", "\n", ". ", "; ", " "]:
                    idx = clean_text.rfind(sep, start + chunk_size // 2, end)
                    if idx != -1:
                        break_point = idx + len(sep)
                        break
                if break_point != -1:
                    end = break_point

            chunk = clean_text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - chunk_overlap if end < text_len else text_len

        return chunks

    async def create_collection(
        self,
        db: AsyncSession,
        user_id: str,
        name: str,
        description: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> KnowledgeCollection:
        col = KnowledgeCollection(
            user_id=user_id,
            project_id=project_id,
            name=name,
            description=description,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(col)
        await db.commit()
        await db.refresh(col)
        return col

    async def list_collections(
        self,
        db: AsyncSession,
        user_id: str,
        project_id: Optional[str] = None
    ) -> List[KnowledgeCollection]:
        stmt = select(KnowledgeCollection).where(KnowledgeCollection.user_id == user_id)
        if project_id:
            stmt = stmt.where((KnowledgeCollection.project_id == project_id) | (KnowledgeCollection.project_id.is_(None)))
        stmt = stmt.order_by(KnowledgeCollection.updated_at.desc())
        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def ingest_document(
        self,
        db: AsyncSession,
        collection_id: str,
        title: str,
        content: str,
        source_type: str = "text",
        file_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: int = 800,
        chunk_overlap: int = 150
    ) -> KnowledgeDocument:
        chunks_text = self.chunk_text(content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        if not chunks_text:
            chunks_text = [content.strip() or "Empty document"]

        # 1. Create document
        doc = KnowledgeDocument(
            collection_id=collection_id,
            title=title,
            source_type=source_type,
            file_path=file_path,
            file_size=len(content.encode("utf-8")),
            total_chunks=len(chunks_text),
            metadata_json=json.dumps(metadata) if metadata else None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(doc)
        await db.flush()  # Populates doc.id

        # 2. Batch generate embeddings for chunks
        embeddings = await embedding_service.get_batch_embeddings(chunks_text)

        # 3. Create chunk entities
        for idx, (chunk_str, emb) in enumerate(zip(chunks_text, embeddings)):
            chunk_entity = DocumentChunk(
                document_id=doc.id,
                chunk_index=idx + 1,
                content=chunk_str,
                token_count=max(1, len(chunk_str) // 4),
                embedding_json=json.dumps(emb),
                metadata_json=json.dumps({"title": title, "index": idx + 1}),
                created_at=datetime.now(timezone.utc)
            )
            db.add(chunk_entity)

        await db.commit()
        await db.refresh(doc)
        return doc

    async def hybrid_search(
        self,
        db: AsyncSession,
        user_id: str,
        query: str,
        collection_ids: Optional[List[str]] = None,
        project_id: Optional[str] = None,
        top_k: int = 5,
        alpha: float = 0.5
    ) -> List[ChunkSearchResult]:
        if not query.strip():
            return []

        # 1. Fetch all accessible chunks for the user
        stmt = (
            select(DocumentChunk, KnowledgeDocument, KnowledgeCollection)
            .join(KnowledgeDocument, DocumentChunk.document_id == KnowledgeDocument.id)
            .join(KnowledgeCollection, KnowledgeDocument.collection_id == KnowledgeCollection.id)
            .where(KnowledgeCollection.user_id == user_id)
        )

        if collection_ids:
            stmt = stmt.where(KnowledgeCollection.id.in_(collection_ids))
        if project_id:
            stmt = stmt.where((KnowledgeCollection.project_id == project_id) | (KnowledgeCollection.project_id.is_(None)))

        res = await db.execute(stmt)
        rows = res.all()

        if not rows:
            return []

        chunks_data = []
        corpus_tokens = []
        for chunk, doc, col in rows:
            tokens = re.findall(r"\b\w+\b", chunk.content.lower())
            corpus_tokens.append(tokens)
            chunks_data.append({
                "chunk": chunk,
                "doc": doc,
                "col": col,
                "embedding": json.loads(chunk.embedding_json) if chunk.embedding_json else None
            })

        # 2. Dense Vector Scoring
        query_vec = await embedding_service.get_embedding(query)
        dense_scores = []
        for item in chunks_data:
            if item["embedding"]:
                sim = embedding_service.cosine_similarity(query_vec, item["embedding"])
            else:
                sim = 0.0
            dense_scores.append(sim)

        # 3. Sparse BM25 Scoring
        query_tokens = re.findall(r"\b\w+\b", query.lower())
        bm25 = BM25Okapi(corpus_tokens)
        bm25_scores = bm25.get_scores(query_tokens)

        # 4. Reciprocal Rank Fusion (RRF)
        # Ranks:
        dense_rank = sorted(range(len(dense_scores)), key=lambda i: dense_scores[i], reverse=True)
        sparse_rank = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)

        dense_rank_map = {idx: rank for rank, idx in enumerate(dense_rank)}
        sparse_rank_map = {idx: rank for rank, idx in enumerate(sparse_rank)}

        rrf_results = []
        k_const = 60.0

        for i, item in enumerate(chunks_data):
            r_dense = dense_rank_map[i]
            r_sparse = sparse_rank_map[i]
            rrf_score = (alpha / (k_const + r_dense)) + ((1.0 - alpha) / (k_const + r_sparse))

            rrf_results.append(ChunkSearchResult(
                chunk_id=item["chunk"].id,
                document_id=item["doc"].id,
                document_title=item["doc"].title,
                collection_id=item["col"].id,
                chunk_index=item["chunk"].chunk_index,
                content=item["chunk"].content,
                score=round(rrf_score, 6),
                dense_score=round(float(dense_scores[i]), 4),
                sparse_score=round(float(bm25_scores[i]), 4)
            ))

        rrf_results.sort(key=lambda x: x.score, reverse=True)
        return rrf_results[:top_k]

    def format_rag_context(self, search_results: List[ChunkSearchResult]) -> Tuple[str, List[Citation]]:
        """Format chunks into structured prompt context with citation mappings."""
        if not search_results:
            return "", []

        context_blocks = []
        citations = []

        for idx, res in enumerate(search_results, start=1):
            context_blocks.append(
                f"[Source {idx}: \"{res.document_title}\" (Section {res.chunk_index})]\n{res.content}"
            )
            citations.append(Citation(
                id=idx,
                document_id=res.document_id,
                source_title=res.document_title,
                chunk_index=res.chunk_index,
                content_snippet=res.content[:160] + ("..." if len(res.content) > 160 else "")
            ))

        formatted_context = "--- RETRIEVED KNOWLEDGE BASE CONTEXT ---\n" + "\n\n".join(context_blocks) + "\n----------------------------------------\n"
        return formatted_context, citations


# Global singleton instance
rag_service = RAGService()
