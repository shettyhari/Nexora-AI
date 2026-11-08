import os
import shutil
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.attachment import Attachment
from app.models.user import User
from app.schemas.attachment import AttachmentResponse

router = APIRouter(prefix="/attachments", tags=["Attachments"])


@router.post("/upload", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Securely upload file or image attachment."""
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # Sanitize and check extension
    original_filename = file.filename or "unnamed_file"
    ext = original_filename.split(".")[-1].lower() if "." in original_filename else "bin"

    # Generate isolated storage path
    file_id = str(uuid.uuid4())
    stored_filename = f"{file_id}.{ext}"
    storage_path = os.path.join(settings.UPLOAD_DIR, stored_filename)

    # Write file content to disk
    file_size = 0
    with open(storage_path, "wb") as buffer:
        while chunk := await file.read(1024 * 64):
            file_size += len(chunk)
            if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                os.remove(storage_path)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB"
                )
            buffer.write(chunk)

    mime_type = file.content_type or "application/octet-stream"
    file_type = "image" if mime_type.startswith("image/") else "document"

    attachment = Attachment(
        id=file_id,
        user_id=current_user.id,
        file_name=original_filename,
        file_type=file_type,
        file_size=file_size,
        storage_path=storage_path,
        mime_type=mime_type
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)

    return attachment


@router.get("/{attachment_id}/download")
async def download_file(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Download or view an attachment (owner-restricted)."""
    query = select(Attachment).where(Attachment.id == attachment_id, Attachment.user_id == current_user.id)
    result = await db.execute(query)
    att = result.scalar_one_or_none()

    if not att or not os.path.exists(att.storage_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    return FileResponse(
        path=att.storage_path,
        filename=att.file_name,
        media_type=att.mime_type
    )

