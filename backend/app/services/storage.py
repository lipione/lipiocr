from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Dict

from app.core.config import get_settings


SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(filename: str) -> str:
    cleaned = SAFE_NAME_RE.sub("-", filename.strip()) or "upload.bin"
    return cleaned[:160]


def _object_key(case_id: str, filename: str) -> str:
    stamp = datetime.utcnow().strftime("%Y/%m/%d/%H%M%S%f")
    return f"cases/{case_id}/original/{stamp}-{_safe_filename(filename)}"


class LocalObjectStorage:
    backend = "local"

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def put_upload(self, *, case_id: str, filename: str, content: bytes, content_type: str) -> Dict[str, object]:
        key = _object_key(case_id, filename)
        target = self.root_dir / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        return {
            "backend": self.backend,
            "bucket": "local",
            "object_key": key,
            "uri": f"local://{key}",
            "etag": digest,
            "sha256": digest,
            "content_type": content_type,
            "size": len(content),
            "local_path": str(target),
        }


class S3ObjectStorage:
    backend = "s3"

    def __init__(self, settings) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("Install S3 dependencies: pip install -e '.[test]'") from exc

        self.bucket = settings.s3_bucket
        self.endpoint_url = settings.s3_endpoint_url or None
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id or None,
            aws_secret_access_key=settings.s3_secret_access_key or None,
        )

    def put_upload(self, *, case_id: str, filename: str, content: bytes, content_type: str) -> Dict[str, object]:
        key = _object_key(case_id, filename)
        digest = hashlib.sha256(content).hexdigest()
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            Metadata={"sha256": digest},
        )
        return {
            "backend": self.backend,
            "bucket": self.bucket,
            "object_key": key,
            "uri": f"s3://{self.bucket}/{key}",
            "etag": digest,
            "sha256": digest,
            "content_type": content_type,
            "size": len(content),
        }


def build_storage(settings=None):
    active_settings = settings or get_settings()
    backend = active_settings.storage_backend
    if backend == "auto":
        backend = "s3" if active_settings.s3_endpoint_url else "local"
    if backend == "s3":
        return S3ObjectStorage(active_settings)
    return LocalObjectStorage(Path(active_settings.upload_dir))
