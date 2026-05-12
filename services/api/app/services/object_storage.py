from io import BytesIO
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error

from app.config import get_settings
from app.domain.enums import ErrorCode


class ObjectStorageError(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def put_upload_bytes(key: str, content: bytes, content_type: str) -> None:
    settings = get_settings()
    _put_bytes(settings.s3_bucket_uploads, key, content, content_type)


def put_artifact_bytes(key: str, content: bytes, content_type: str) -> None:
    settings = get_settings()
    _put_bytes(settings.s3_bucket_artifacts, key, content, content_type)


def get_upload_bytes(key: str) -> bytes:
    settings = get_settings()
    return _get_bytes(
        settings.s3_bucket_uploads,
        key,
        ErrorCode.STORAGE_READ_FAILED,
        f"Could not read upload from storage: {key}",
    )


def get_artifact_bytes(key: str) -> bytes:
    settings = get_settings()
    return _get_bytes(
        settings.s3_bucket_artifacts,
        key,
        ErrorCode.STORAGE_READ_FAILED,
        f"Could not read artifact from storage: {key}",
    )


def _get_bytes(bucket: str, key: str, code: ErrorCode, message: str) -> bytes:
    try:
        response = _client().get_object(bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
    except S3Error as exc:
        raise ObjectStorageError(code, message) from exc


def _put_bytes(bucket: str, key: str, content: bytes, content_type: str) -> None:
    try:
        _client().put_object(
            bucket,
            key,
            BytesIO(content),
            length=len(content),
            content_type=content_type,
        )
    except S3Error as exc:
        raise ObjectStorageError(ErrorCode.STORAGE_WRITE_FAILED, f"Could not write object to storage: {key}") from exc


def _client() -> Minio:
    settings = get_settings()
    parsed = urlparse(settings.s3_endpoint)
    endpoint = parsed.netloc or parsed.path
    secure = parsed.scheme == "https"
    return Minio(
        endpoint,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        secure=secure,
        region=settings.s3_region,
    )
