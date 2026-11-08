from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import MessageResponse as SimpleResponse
from app.services.rag.rag_service import rag_service

router = APIRouter(prefix="/rag", tags=["RAG"])


class CollectionCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    project_id: Optional[str] = None


class DocumentIngestRequest(BaseModel):
    title: str
    content: str
    source_type: str = "text"
    metadata: Optional[Dict[str, Any]] = None


class HybridSearchRequest(BaseModel):
    query: str
    collection_ids: Optional[List[str]] = None
    project_id: Optional[str] = None
    top_k: int = 5
    alpha: float = 0.5


@router.get("/collections", response_model=List[Dict[str, Any]])
async def list_collections(
    project_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List knowledge collections belonging to the current user."""
    cols = await rag_service.list_collections(db=db, user_id=current_user.id, project_id=project_id)
    return [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "project_id": c.project_id,
            "created_at": c.created_at.isoformat() if c.created_at else None
        }
        for c in cols
    ]


@router.post("/collections", status_code=status.HTTP_201_CREATED, response_model=Dict[str, Any])
async def create_collection(
    data: CollectionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new knowledge collection."""
    col = await rag_service.create_collection(
        db=db,
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        project_id=data.project_id
    )
    return {
        "id": col.id,
        "name": col.name,
        "description": col.description,
        "project_id": col.project_id
    }


@router.post("/collections/{collection_id}/documents", status_code=status.HTTP_201_CREATED, response_model=Dict[str, Any])
async def ingest_document(
    collection_id: str,
    data: DocumentIngestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Ingest, chunk, embed, and index a document into a collection."""
    doc = await rag_service.ingest_document(
        db=db,
        collection_id=collection_id,
        title=data.title,
        content=data.content,
        source_type=data.source_type,
        metadata=data.metadata
    )
    return {
        "id": doc.id,
        "collection_id": doc.collection_id,
        "title": doc.title,
        "total_chunks": doc.total_chunks,
        "file_size": doc.file_size
    }


@router.post("/search", response_model=List[Dict[str, Any]])
async def search_knowledge(
    data: HybridSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Execute hybrid BM25 + dense vector semantic search with RRF reranking."""
    results = await rag_service.hybrid_search(
        db=db,
        user_id=current_user.id,
        query=data.query,
        collection_ids=data.collection_ids,
        project_id=data.project_id,
        top_k=data.top_k,
        alpha=data.alpha
    )
    return [r.model_dump() for r in results]

