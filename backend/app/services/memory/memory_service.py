import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.memory import Memory
from app.services.embedding.embedding_service import embedding_service

logger = logging.getLogger(__name__)


class MemorySearchResult(BaseModel):
    id: str
    user_id: str
    content: str
    memory_type: str
    category: str
    confidence: float
    similarity: float
    created_at: datetime
    project_id: Optional[str] = None


class MemoryService:
    """Enterprise Memory Engine managing short-term, long-term, and project semantic memory."""

    async def store_memory(
        self,
        db: AsyncSession,
        user_id: str,
        content: str,
        memory_type: str = "long_term",
        category: str = "fact",
        project_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Memory:
        clean_content = content.strip()
        if not clean_content:
            raise ValueError("Memory content cannot be empty")

        # 1. Generate embedding
        embedding = await embedding_service.get_embedding(clean_content)
        embedding_json = json.dumps(embedding)

        # 2. Duplicate Detection via Semantic Similarity
        # Query existing active memories for this user in the same category/project
        stmt = select(Memory).where(
            Memory.user_id == user_id,
            Memory.is_active.is_(True)
        )
        if project_id:
            stmt = stmt.where(Memory.project_id == project_id)

        result = await db.execute(stmt)
        existing_memories = result.scalars().all()

        highest_similarity = 0.0
        duplicate_candidate: Optional[Memory] = None

        for mem in existing_memories:
            if not mem.embedding_json:
                continue
            try:
                mem_vec = json.loads(mem.embedding_json)
                sim = embedding_service.cosine_similarity(embedding, mem_vec)
                if sim > highest_similarity:
                    highest_similarity = sim
                    duplicate_candidate = mem
            except Exception:
                continue

        # If similarity exceeds duplicate threshold (0.88), update existing memory
        if duplicate_candidate and highest_similarity >= 0.88:
            logger.info(f"Duplicate memory detected (similarity={highest_similarity:.3f}). Updating memory {duplicate_candidate.id}.")
            duplicate_candidate.content = clean_content
            duplicate_candidate.confidence = max(duplicate_candidate.confidence, confidence)
            duplicate_candidate.embedding_json = embedding_json
            duplicate_candidate.updated_at = datetime.now(timezone.utc)
            duplicate_candidate.last_accessed_at = datetime.now(timezone.utc)
            if metadata:
                duplicate_candidate.metadata_json = json.dumps(metadata)
            await db.commit()
            await db.refresh(duplicate_candidate)
            return duplicate_candidate

        # Otherwise insert fresh memory
        new_memory = Memory(
            user_id=user_id,
            project_id=project_id,
            conversation_id=conversation_id,
            memory_type=memory_type,
            category=category,
            content=clean_content,
            confidence=confidence,
            embedding_json=embedding_json,
            metadata_json=json.dumps(metadata) if metadata else None,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            last_accessed_at=datetime.now(timezone.utc)
        )
        db.add(new_memory)
        await db.commit()
        await db.refresh(new_memory)
        return new_memory

    async def retrieve_relevant_memories(
        self,
        db: AsyncSession,
        user_id: str,
        query: str,
        project_id: Optional[str] = None,
        top_k: int = 5,
        min_similarity: float = 0.50
    ) -> List[MemorySearchResult]:
        if not query.strip():
            return []

        query_vec = await embedding_service.get_embedding(query)

        # Retrieve user's memories with strict isolation
        stmt = select(Memory).where(
            Memory.user_id == user_id,
            Memory.is_active.is_(True)
        )
        if project_id:
            stmt = stmt.where((Memory.project_id == project_id) | (Memory.project_id.is_(None)))

        result = await db.execute(stmt)
        memories = result.scalars().all()

        scored: List[MemorySearchResult] = []
        now = datetime.now(timezone.utc)

        for mem in memories:
            if not mem.embedding_json:
                continue
            try:
                mem_vec = json.loads(mem.embedding_json)
                sim = embedding_service.cosine_similarity(query_vec, mem_vec)
                if sim >= min_similarity:
                    scored.append(MemorySearchResult(
                        id=mem.id,
                        user_id=mem.user_id,
                        content=mem.content,
                        memory_type=mem.memory_type,
                        category=mem.category,
                        confidence=mem.confidence,
                        similarity=round(sim, 4),
                        created_at=mem.created_at,
                        project_id=mem.project_id
                    ))
                    # Update access timestamp
                    mem.last_accessed_at = now
            except Exception:
                continue

        await db.commit()

        # Sort descending by similarity
        scored.sort(key=lambda x: x.similarity, reverse=True)
        return scored[:top_k]

    async def list_memories(
        self,
        db: AsyncSession,
        user_id: str,
        category: Optional[str] = None,
        memory_type: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Memory]:
        stmt = select(Memory).where(
            Memory.user_id == user_id,
            Memory.is_active.is_(True)
        ).order_by(Memory.updated_at.desc()).limit(limit)

        if category:
            stmt = stmt.where(Memory.category == category)
        if memory_type:
            stmt = stmt.where(Memory.memory_type == memory_type)
        if project_id:
            stmt = stmt.where(Memory.project_id == project_id)

        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def delete_memory(self, db: AsyncSession, user_id: str, memory_id: str) -> bool:
        """User-controlled memory deletion with permission verification."""
        stmt = select(Memory).where(
            Memory.id == memory_id,
            Memory.user_id == user_id
        )
        res = await db.execute(stmt)
        mem = res.scalar_one_or_none()
        if not mem:
            return False

        await db.delete(mem)
        await db.commit()
        return True

    async def clear_memories(
        self,
        db: AsyncSession,
        user_id: str,
        memory_type: Optional[str] = None
    ) -> int:
        stmt = delete(Memory).where(Memory.user_id == user_id)
        if memory_type:
            stmt = stmt.where(Memory.memory_type == memory_type)
        res = await db.execute(stmt)
        await db.commit()
        return res.rowcount or 0


# Global singleton instance
memory_service = MemoryService()

