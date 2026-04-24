"""Image storage: local filesystem or S3-compatible object storage."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import boto3
from botocore.config import Config

from .settings import settings


class Storage(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes, content_type: str) -> str:
        """Persist bytes and return a URL path or absolute URL for API clients."""


class LocalStorage(Storage):
    def save(self, key: str, data: bytes, content_type: str) -> str:
        base = Path(settings.upload_dir)
        base.mkdir(parents=True, exist_ok=True)
        path = base / key
        path.write_bytes(data)
        return f'/media/{key}'


class S3Storage(Storage):
    def __init__(self) -> None:
        extra: dict = {
            'service_name': 's3',
            'region_name': settings.aws_region or 'us-east-1',
            'config': Config(signature_version='s3v4'),
        }
        if settings.aws_access_key_id:
            extra['aws_access_key_id'] = settings.aws_access_key_id
        if settings.aws_secret_access_key:
            extra['aws_secret_access_key'] = settings.aws_secret_access_key
        if settings.aws_endpoint_url:
            extra['endpoint_url'] = settings.aws_endpoint_url
        self._client = boto3.client(**extra)
        self._bucket = settings.s3_bucket_name.strip()
        self._public_base = settings.media_public_base_url.rstrip('/')

    def save(self, key: str, data: bytes, content_type: str) -> str:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return f'{self._public_base}/{key}'


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = S3Storage() if settings.storage_backend == 's3' else LocalStorage()
    return _storage


def reset_storage_cache() -> None:
    """Used in tests to pick up new settings."""
    global _storage
    _storage = None
