import os
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security_guards import (
    FORCE_ATTACHMENT_DOWNLOAD_EXTENSIONS,
    is_path_within_base,
    record_security_event,
    sanitize_filename,
    validate_upload_extension,
)
from app.models.attachment import Attachment
from app.models.user import User
from app.schemas.attachment import AttachmentResponse
from app.services.billing_service import billing_service
from app.services.storage.object_storage import object_storage

router = APIRouter(prefix="/attachments", tags=["Attachments"])


@router.post("/upload", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Securely upload file or image attachment with extension & plan size enforcement."""
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    safe_name = sanitize_filename(file.filename)
    try:
        ext = validate_upload_extension(safe_name)
    except HTTPException as exc:
        await record_security_event(
            db,
            event_type="forbidden_file_upload_blocked",
            severity="medium",
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            endpoint="/api/v1/attachments/upload",
            details={"filename": safe_name},
        )
        await db.commit()
        raise exc

    # Resolve user's plan upload limit (falling back safely to global setting ceiling)
    _, plan = await billing_service.get_or_create_subscription(db, current_user.id)
    max_mb = min(settings.MAX_FILE_SIZE_MB, plan.max_file_size_mb) if current_user.role != "admin" else settings.MAX_FILE_SIZE_MB
    max_bytes = max(1, max_mb) * 1024 * 1024

    file_id = str(uuid.uuid4())
    stored_filename = f"{file_id}.{ext}"

    chunks = []
    file_size = 0
    while chunk := await file.read(1024 * 64):
        file_size += len(chunk)
        if file_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds your plan's maximum upload size of {max_mb}MB",
            )
        chunks.append(chunk)

    raw_bytes = b"".join(chunks)
    storage_path = object_storage.put_bytes(
        stored_filename,
        raw_bytes,
        content_type=file.content_type or "application/octet-stream",
    )

    mime_type = file.content_type or "application/octet-stream"
    file_type = "image" if mime_type.startswith("image/") else "document"

    attachment = Attachment(
        id=file_id,
        user_id=current_user.id,
        file_name=safe_name,
        file_type=file_type,
        file_size=file_size,
        storage_path=storage_path,
        mime_type=mime_type,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment


@router.get("/{attachment_id}/download")
async def download_file(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download an owner-restricted attachment with nosniff & safe Content-Disposition headers."""
    query = select(Attachment).where(
        Attachment.id == attachment_id,
        Attachment.user_id == current_user.id,
    )
    result = await db.execute(query)
    att = result.scalar_one_or_none()

    if not att or not os.path.exists(att.storage_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    if not is_path_within_base(att.storage_path, settings.UPLOAD_DIR):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid attachment storage path")

    safe_dl_name = sanitize_filename(att.file_name)
    ext = safe_dl_name.rsplit(".", 1)[-1].lower() if "." in safe_dl_name else ""
    force_attach = ext in FORCE_ATTACHMENT_DOWNLOAD_EXTENSIONS or "svg" in (att.mime_type or "").lower()

    resp = FileResponse(
        path=att.storage_path,
        filename=safe_dl_name,
        media_type="application/octet-stream" if force_attach else att.mime_type,
        content_disposition_type="attachment" if force_attach else "inline",
    )
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp
