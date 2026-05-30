from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.app_context import settings
from app.main import app
from app.security.upload_policy import UploadPolicy, validate_upload_policy


def test_rejects_empty_upload():
    try:
        validate_upload_policy("citizenship.jpg", "image/jpeg", b"", UploadPolicy())
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("empty upload should fail")


def test_rejects_oversized_upload():
    policy = UploadPolicy(max_bytes=4, allowed_mime_types={"image/jpeg"}, allowed_extensions={".jpg", ".jpeg"})
    try:
        validate_upload_policy("citizenship.jpg", "image/jpeg", b"12345", policy)
    except HTTPException as exc:
        assert exc.status_code == 413
    else:
        raise AssertionError("oversized upload should fail")


def test_rejects_unsupported_mime_and_extension():
    policy = UploadPolicy(max_bytes=1024, allowed_mime_types={"image/jpeg"}, allowed_extensions={".jpg"})
    try:
        validate_upload_policy("script.exe", "application/x-msdownload", b"123", policy)
    except HTTPException as exc:
        assert exc.status_code == 415
    else:
        raise AssertionError("unsupported upload should fail")


def test_document_upload_rejects_unsupported_content_type():
    original_enabled = settings.api_auth_enabled
    try:
        settings.api_auth_enabled = False
        client = TestClient(app)
        response = client.post(
            "/api/documents/upload",
            data={"declared_document_type": "unknown"},
            files={"file": ("script.exe", b"malware", "application/x-msdownload")},
        )

        assert response.status_code == 415
        assert response.json()["detail"] == "Upload file extension is not supported"
    finally:
        settings.api_auth_enabled = original_enabled
