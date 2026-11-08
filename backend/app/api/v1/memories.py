from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import MessageResponse as SimpleResponse
from app.services.memory.memory_service import memory_service

router = APIRouter(prefix="/memories", tags=["Memory"])


class MemoryCreateRequest(BaseModel):
    content: str
    memory_type: str = "long_term"  # "short_term", "long_term", "project", "user_preference"
    category: str = "fact"  # "preference", "fact", "project_context", "personal", "technical"
    project_id: Optional[str] = None
    conversation_id: Optional[str] = None
    confidence: float = 1.0


class MemorySearchRequest(BaseModel):
    query: str
    project_id: Optional[str] = None
    top_k: int = 5
    min_similarity: float = 0.50


@router.get("", response_model=List[Dict[str, Any]])
async def list_user_memories(
    category: Optional[str] = Query(None),
    memory_type: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all active memories for the authenticated user."""
    memories = await memory_service.list_memories(
        db=db,
        user_id=current_user.id,
        category=category,
        memory_type=memory_type,
        project_id=project_id
    )
    return [
        {
            "id": m.id,
            "content": m.content,
            "memory_type": m.memory_type,
            "category": m.category,
            "confidence": m.confidence,
            "project_id": m.project_id,
            "conversation_id": m.conversation_id,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            "last_accessed_at": m.last_accessed_at.isoformat() if m.last_accessed_at else None
        }
        for m in memories
    ]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Dict[str, Any])
async def create_memory(
    data: MemoryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Store or update a user memory with automatic duplicate detection."""
    memory = await memory_service.store_memory(
        db=db,
        user_id=current_user.id,
        content=data.content,
        memory_type=data.memory_type,
        category=data.category,
        project_id=data.project_id,
        conversation_id=data.conversation_id,
        confidence=data.confidence
    )
    return {
        "id": memory.id,
        "content": memory.content,
        "memory_type": memory.memory_type,
        "category": memory.category,
        "confidence": memory.confidence,
        "project_id": memory.project_id
    }


@router.post("/search", response_model=List[Dict[str, Any]])
async def search_memories(
    data: MemorySearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Semantic vector search across authenticated user's memories."""
    results = await memory_service.retrieve_relevant_memories(
        db=db,
        user_id=current_user.id,
        query=data.query,
        project_id=data.project_id,
        top_k=data.top_k,
        min_similarity=data.min_similarity
    )
    return [r.model_dump() for r in results]


@router.delete("/{memory_id}", response_model=SimpleResponse)
async def delete_memory(
    memory_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a memory with strict user-tenant isolation."""
    success = await memory_service.delete_memory(db=db, user_id=current_user.id, memory_id=memory_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found or access denied")
    return SimpleResponse(message="Memory successfully deleted")


@router.delete("", response_model=SimpleResponse)
async def clear_all_memories(
    memory_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Clear all memories for the user."""
    count = await memory_service.clear_memories(db=db, user_id=current_user.id, memory_type=memory_type)
    return SimpleResponse(message=f"Successfully cleared {count} memories")

