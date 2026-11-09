"""
Object storage abstraction supporting S3-compatible stores (AWS S3 / MinIO / Cloudflare R2)
with zero-dependency local filesystem storage fallback.
"""
import logging
import os
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.security_guards import is_path_within_base

logger = logging.getLogger(__name__)


class ObjectStorageService:
    """Unified object storage interface for uploads, checkpoints, and backups."""

    def __init__(self) -> None:
        self.base_dir = os.path.realpath(settings.UPLOAD_DIR)
        os.makedirs(self.base_dir, exist_ok=True)
        self._s3_client = None

    def _get_s3_client(self):
        if self._s3_client is not None:
            return self._s3_client
        if settings.STORAGE_BACKEND.lower() != "s3":
            return None
        try:
            import boto3
            kwargs: Dict[str, Any] = {
                "region_name": settings.S3_REGION or "us-east-1",
            }
            if settings.S3_ENDPOINT_URL:
                kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
            if settings.S3_ACCESS_KEY_ID and settings.S3_SECRET_ACCESS_KEY:
                kwargs["aws_access_key_id"] = settings.S3_ACCESS_KEY_ID
                kwargs["aws_secret_access_key"] = settings.S3_SECRET_ACCESS_KEY
            self._s3_client = boto3.client("s3", **kwargs)
            return self._s3_client
        except Exception as exc:
            logger.warning(f"S3 client unavailable, using local storage: {exc}")
            return None

    def put_bytes(self, object_key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Persist bytes cleanly and return storage URI or safe local path."""
        clean_key = object_key.replace("\\", "/").lstrip("/")
        s3 = self._get_s3_client()
        if s3 is not None and settings.S3_BUCKET:
            s3.put_object(
                Bucket=settings.S3_BUCKET,
                Key=clean_key,
                Body=data,
                ContentType=content_type,
            )
            return f"s3://{settings.S3_BUCKET}/{clean_key}"

        dest = os.path.realpath(os.path.join(self.base_dir, clean_key))
        if not is_path_within_base(dest, self.base_dir):
            raise PermissionError("Storage path violates confinement boundary.")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
        return dest

    def get_bytes(self, storage_path: str) -> bytes:
        """Read object bytes from S3 URI or local path."""
        if storage_path.startswith("s3://"):
            s3 = self._get_s3_client()
            if s3 is None:
                raise RuntimeError("S3 client is not configured.")
            without_scheme = storage_path[5:]
            bucket, key = without_scheme.split("/", 1)
            resp = s3.get_object(Bucket=bucket, Key=key)
            return resp["Body"].read()

        if not is_path_within_base(storage_path, self.base_dir):
            raise PermissionError("Storage read violates confinement boundary.")
        with open(storage_path, "rb") as f:
            return f.read()

    def delete_object(self, storage_path: str) -> bool:
        """Delete object cleanly during GDPR / conversation purge."""
        try:
            if storage_path.startswith("s3://"):
                s3 = self._get_s3_client()
                if s3 is None:
                    return False
                bucket, key = storage_path[5:].split("/", 1)
                s3.delete_object(Bucket=bucket, Key=key)
                return True

            if os.path.exists(storage_path) and (
                is_path_within_base(storage_path, self.base_dir)
                or is_path_within_base(storage_path, settings.BACKUP_DIR)
            ):
                os.remove(storage_path)
                return True
        except Exception as exc:
            logger.warning(f"Failed deleting storage object '{storage_path}': {exc}")
        return False

    def health_check(self) -> Dict[str, Any]:
        backend = settings.STORAGE_BACKEND.lower()
        is_s3 = backend == "s3" and self._get_s3_client() is not None
        writable = os.access(self.base_dir, os.W_OK)
        return {
            "backend": backend if is_s3 else "local",
            "status": "connected" if is_s3 else ("writable" if writable else "read_only"),
            "local_dir": self.base_dir,
            "s3_bucket": settings.S3_BUCKET if backend == "s3" else None,
            "writable": writable,
        }


object_storage = ObjectStorageService()
