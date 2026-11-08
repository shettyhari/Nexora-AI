import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.attachment import Attachment
from app.models.user import User
from app.services.document.document_service import document_intelligence_service
from app.services.rag.rag_service import rag_service

router = APIRouter(prefix="/documents", tags=["Document Intelligence"])


class DocumentParseRequest(BaseModel):
    attachment_id: Optional[str] = None
    file_path: Optional[str] = None


class DocumentCompareRequest(BaseModel):
    attachment_id_1: Optional[str] = None
    attachment_id_2: Optional[str] = None
    file_path_1: Optional[str] = None
    file_path_2: Optional[str] = None
    focus_topic: Optional[str] = None


class DocumentRAGIngestRequest(BaseModel):
    attachment_id: str
    collection_id: Optional[str] = None


async def _resolve_file_path(req_path: Optional[str], attachment_id: Optional[str], user_id: str, db: AsyncSession) -> str:
    if req_path and os.path.exists(req_path):
        return req_path
    if attachment_id:
        from sqlalchemy import select
        q = select(Attachment).where(Attachment.id == attachment_id, Attachment.user_id == user_id)
        res = await db.execute(q)
        att = res.scalar_one_or_none()
        if att and os.path.exists(att.storage_path):
            return att.storage_path
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target document file not found or inaccessible.")


@router.post("/parse")
async def parse_document(
    req: DocumentParseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Parse document and return structured text, metadata, and extracted tables."""
    path = await _resolve_file_path(req.file_path, req.attachment_id, current_user.id, db)
    try:
        doc = document_intelligence_service.parse_file(path)
        return {
            "success": True,
            "data": doc.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/tables")
async def extract_tables(
    req: DocumentParseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Extract tabular datasets from a document and format as Markdown & JSON."""
    path = await _resolve_file_path(req.file_path, req.attachment_id, current_user.id, db)
    try:
        doc = document_intelligence_service.parse_file(path)
        return {
            "file_name": doc.file_name,
            "table_count": len(doc.tables),
            "tables": [t.dict() for t in doc.tables]
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/compare")
async def compare_documents(
    req: DocumentCompareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Perform side-by-side comparative analysis between two documents."""
    path1 = await _resolve_file_path(req.file_path_1, req.attachment_id_1, current_user.id, db)
    path2 = await _resolve_file_path(req.file_path_2, req.attachment_id_2, current_user.id, db)

    try:
        doc1 = document_intelligence_service.parse_file(path1)
        doc2 = document_intelligence_service.parse_file(path2)
        comp = document_intelligence_service.compare_documents(doc1, doc2, req.focus_topic)
        return {
            "success": True,
            "comparison": comp.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/rag-ingest")
async def ingest_to_rag(
    req: DocumentRAGIngestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Ingest an uploaded document into the RAG knowledge index for semantic search."""
    path = await _resolve_file_path(None, req.attachment_id, current_user.id, db)
    doc = document_intelligence_service.parse_file(path)

    # Use default user collection if collection_id not specified
    collection_id = req.collection_id
    if not collection_id:
        collections = await rag_service.list_collections(current_user.id, db=db)
        if collections:
            collection_id = collections[0].id
        else:
            new_col = await rag_service.create_collection(
                name="My Documents",
                user_id=current_user.id,
                description="Default collection for document intelligence uploads",
                db=db
            )
            collection_id = new_col.id

    rag_doc = await rag_service.ingest_document(
        collection_id=collection_id,
        user_id=current_user.id,
        title=doc.file_name,
        raw_text=doc.text_content,
        source_type=doc.file_type,
        file_path=path,
        db=db
    )

    return {
        "success": True,
        "message": f"Document '{doc.file_name}' ingested successfully into RAG.",
        "knowledge_document_id": rag_doc.id,
        "collection_id": collection_id,
        "total_words": doc.total_words
    }
