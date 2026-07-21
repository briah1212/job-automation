from __future__ import annotations

import io
import logging
from typing import Optional

from minio import Minio
from minio.error import S3Error

from app.core.config import settings

logger = logging.getLogger(__name__)


class ObjectStorage:
    """Thin wrapper around the MinIO client, scoped to one bucket.

    Ensures the bucket exists on first use rather than requiring a separate
    provisioning step, since this is the first thing in the codebase to
    actually talk to MinIO (it's been running unused in docker-compose).
    """

    def __init__(self, bucket: str):
        self._bucket = bucket
        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
                logger.info("Created object storage bucket %s", self._bucket)
        except S3Error as exc:
            logger.error("Failed to ensure bucket %s exists: %s", self._bucket, exc)
            raise

    def put_bytes(self, object_key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Upload raw bytes, returning the object key."""
        self._client.put_object(
            self._bucket,
            object_key,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return object_key

    def get_bytes(self, object_key: str) -> bytes:
        response = self._client.get_object(self._bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()


_browser_artifacts_storage: Optional[ObjectStorage] = None


def get_browser_artifacts_storage() -> ObjectStorage:
    """Lazily-constructed singleton for the browser-checkpoint screenshot bucket."""
    global _browser_artifacts_storage
    if _browser_artifacts_storage is None:
        _browser_artifacts_storage = ObjectStorage(settings.minio_browser_bucket)
    return _browser_artifacts_storage
