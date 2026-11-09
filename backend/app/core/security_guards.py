"""
Security guards for filename sanitization, path traversal confinement,
and persisted SecurityEvent telemetry logging.
"""
import json
import logging
import os
import re
from typing import Any, Dict, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.attachment import Attachment

logger = logging.getLogger("nexora.security")

# Dangerous active script / executable file types rejected at upload boundaries
FORBIDDEN_UPLOAD_EXTENSIONS = {
    "exe", "dll", "bat", "cmd", "sh", "bash", "ps1", "vbs", "vbe",
    "msi", "scr", "com", "pif", "cpl", "hta", "jar", "php", "jsp",
    "asp", "aspx", "cgi", "html", "htm", "xhtml"
}

# Scriptable / active extensions that MUST be served as attachment + nosniff on download
FORCE_ATTACHMENT_DOWNLOAD_EXTENSIONS = {
    "svg", "xml", "js", "ts", "tsx", "jsx", "py", "html", "htm", "xhtml", "json", "md"
}


def sanitize_filename(filename: Optional[str]) -> str:
    """Strip path traversal components and control characters from user filenames."""
    raw = (filename or "unnamed_file").replace("\x00", "")
    # Split on both POSIX and Windows separators and take the basename
    base = os.path.basename(raw.replace("\\", "/")).strip()
    if not base or base in (".", ".."):
        base = "unnamed_file"
    # Replace unsafe filesystem chars while preserving extension dot and hyphens
    cleaned = re.sub(r"[^a-zA-Z0-9._ -]", "_", base)
    cleaned = cleaned.lstrip(".") or "unnamed_file"
    return cleaned[:200]


def validate_upload_extension(filename: str) -> str:
    """Validate extension against allowlist and explicit deny list. Returns lowercase extension."""
    cleaned = sanitize_filename(filename)
    if "." not in cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have an explicit allowed extension."
        )
    ext = cleaned.rsplit(".", 1)[-1].lower()
    if ext in FORBIDDEN_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security policy blocks potentially dangerous file extension '.{ext}'."
        )
    allowed = {e.lower() for e in settings.ALLOWED_EXTENSIONS}
    if ext not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '.{ext}'. Allowed formats: {', '.join(sorted(allowed))}"
        )
    return ext


def is_path_within_base(candidate_path: str, base_dir: str) -> bool:
    """Strictly verify candidate_path resolves inside base_dir using realpath + commonpath."""
    try:
        real_base = os.path.normcase(os.path.realpath(base_dir))
        real_cand = os.path.normcase(os.path.realpath(candidate_path))
        return os.path.commonpath([real_base, real_cand]) == real_base
    except Exception:
        return False


def ensure_safe_storage_path(file_path: str) -> str:
    """Synchronous storage confinement validator for upload/tool boundaries."""
    if not file_path or "\x00" in file_path:
        raise PermissionError("Invalid empty or malformed file path.")
    upload_root = os.path.realpath(settings.UPLOAD_DIR)
    os.makedirs(upload_root, exist_ok=True)
    if not is_path_within_base(file_path, upload_root):
        raise PermissionError(
            "Security Policy Violation: Access to paths outside authorized upload storage is denied."
        )
    resolved = os.path.realpath(file_path)
    if not os.path.isfile(resolved):
        raise FileNotFoundError("Target file does not exist.")
    return resolved


async def record_security_event(
    db: Optional[AsyncSession],
    event_type: str,
    severity: str = "medium",
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    endpoint: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist structured security telemetry event safely without breaking request flow."""
    logger.warning(
        f"SecurityEvent type={event_type} severity={severity} user_id={user_id} endpoint={endpoint}"
    )
    if db is None:
        return
    try:
        from app.models.ecosystem import SecurityEvent
        evt = SecurityEvent(
            user_id=user_id,
            event_type=event_type,
            severity=severity,
            ip_address=ip_address,
            endpoint=endpoint,
            details=details or {},
        )
        db.add(evt)
        await db.flush()
    except Exception as exc:
        logger.debug(f"Could not persist SecurityEvent: {exc}")


async def resolve_safe_file_path(
    req_path: Optional[str],
    attachment_id: Optional[str],
    user_id: str,
    db: AsyncSession,
    endpoint: str = "file_access",
) -> str:
    """
    Resolve an owned Attachment or confined path inside UPLOAD_DIR.
    Rejects directory traversal (`../`, `.env`, `/etc/passwd`, foreign files) with HTTP 403/404.
    """
    upload_root = os.path.realpath(settings.UPLOAD_DIR)
    os.makedirs(upload_root, exist_ok=True)

    if attachment_id:
        res = await db.execute(
            select(Attachment).where(Attachment.id == attachment_id, Attachment.user_id == user_id)
        )
        att = res.scalar_one_or_none()
        if not att:
            await record_security_event(
                db,
                event_type="unauthorized_file_access",
                severity="medium",
                user_id=user_id,
                endpoint=endpoint,
                details={"attachment_id": attachment_id},
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target attachment not found or access denied.",
            )
        if not is_path_within_base(att.storage_path, upload_root):
            await record_security_event(
                db,
                event_type="path_traversal_blocked",
                severity="high",
                user_id=user_id,
                endpoint=endpoint,
                details={"attachment_id": attachment_id},
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: attachment storage path violates confinement boundary.",
            )
        resolved = os.path.realpath(att.storage_path)
        if not os.path.exists(resolved):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found.")
        return resolved

    if req_path:
        if "\x00" in req_path or ".." in req_path.replace("\\", "/").split("/"):
            await record_security_event(
                db,
                event_type="path_traversal_blocked",
                severity="high",
                user_id=user_id,
                endpoint=endpoint,
                details={"attempted_path": req_path[:120]},
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: path traversal attempt blocked.",
            )

        # Check confinement inside UPLOAD_DIR
        if not is_path_within_base(req_path, upload_root):
            await record_security_event(
                db,
                event_type="path_traversal_blocked",
                severity="high",
                user_id=user_id,
                endpoint=endpoint,
                details={"attempted_path": req_path[:120]},
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: file path outside authorized user storage.",
            )

        resolved = os.path.realpath(req_path)
        if not os.path.isfile(resolved):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target file not found.",
            )

        # Also enforce ownership if an Attachment record maps to this path
        owner_res = await db.execute(
            select(Attachment).where(Attachment.storage_path == req_path)
        )
        att_record = owner_res.scalar_one_or_none()
        if att_record and att_record.user_id != user_id:
            await record_security_event(
                db,
                event_type="tenant_file_isolation_blocked",
                severity="high",
                user_id=user_id,
                endpoint=endpoint,
                details={"attachment_id": att_record.id},
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: file belongs to another user.",
            )

        return resolved

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target file not found.")
