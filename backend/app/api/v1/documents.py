from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security_guards import resolve_safe_file_path
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


@router.post("/parse")
async def parse_document(
    req: DocumentParseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Parse document and return structured text, metadata, and extracted tables."""
    path = await resolve_safe_file_path(
        req.file_path, req.attachment_id, current_user.id, db, endpoint="/api/v1/documents/parse"
    )
    try:
        doc = document_intelligence_service.parse_file(path)
        return {"success": True, "data": doc.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/tables")
async def extract_tables(
    req: DocumentParseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Extract tabular datasets from a document and format as Markdown & JSON."""
    path = await resolve_safe_file_path(
        req.file_path, req.attachment_id, current_user.id, db, endpoint="/api/v1/documents/tables"
    )
    try:
        doc = document_intelligence_service.parse_file(path)
        return {
            "file_name": doc.file_name,
            "table_count": len(doc.tables),
            "tables": [t.model_dump() for t in doc.tables],
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/compare")
async def compare_documents(
    req: DocumentCompareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Perform side-by-side comparative analysis between two documents."""
    path1 = await resolve_safe_file_path(
        req.file_path_1, req.attachment_id_1, current_user.id, db, endpoint="/api/v1/documents/compare"
    )
    path2 = await resolve_safe_file_path(
        req.file_path_2, req.attachment_id_2, current_user.id, db, endpoint="/api/v1/documents/compare"
    )

    try:
        doc1 = document_intelligence_service.parse_file(path1)
        doc2 = document_intelligence_service.parse_file(path2)
        comp = document_intelligence_service.compare_documents(doc1, doc2, req.focus_topic)
        return {"success": True, "comparison": comp.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/rag-ingest")
async def ingest_to_rag(
    req: DocumentRAGIngestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ingest an uploaded document into the RAG knowledge index for semantic search."""
    path = await resolve_safe_file_path(
        None, req.attachment_id, current_user.id, db, endpoint="/api/v1/documents/rag-ingest"
    )
    doc = document_intelligence_service.parse_file(path)

    collection_id = req.collection_id
    if not collection_id:
        collections = await rag_service.list_collections(db, current_user.id)
        if collections:
            collection_id = collections[0].id
        else:
            new_col = await rag_service.create_collection(
                db=db,
                user_id=current_user.id,
                name="My Documents",
                description="Default collection for document intelligence uploads",
            )
            collection_id = new_col.id

    rag_doc = await rag_service.ingest_document(
        db=db,
        collection_id=collection_id,
        title=doc.file_name,
        content=doc.text_content,
        source_type=doc.file_type,
        file_path=path,
    )

    return {
        "success": True,
        "message": f"Document '{doc.file_name}' ingested successfully into RAG.",
        "knowledge_document_id": rag_doc.id,
        "collection_id": collection_id,
        "total_words": doc.total_words,
    }
