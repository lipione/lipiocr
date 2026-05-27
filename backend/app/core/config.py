import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "LipiOCR Enterprise"
    environment: str = os.getenv("LIPIOCR_ENVIRONMENT", "development")
    cors_origins: str = os.getenv("LIPIOCR_CORS_ORIGINS", "http://localhost:3000")
    upload_dir: Path = Path(os.getenv("LIPIOCR_UPLOAD_DIR", "storage/uploads"))
    repository_backend: str = os.getenv("LIPIOCR_REPOSITORY_BACKEND", "auto")
    database_url: str = os.getenv("DATABASE_URL", "")
    storage_backend: str = os.getenv("LIPIOCR_STORAGE_BACKEND", "auto")
    s3_endpoint_url: str = os.getenv("S3_ENDPOINT_URL", "")
    s3_bucket: str = os.getenv("S3_BUCKET", "lipiocr-documents")
    s3_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", os.getenv("MINIO_ROOT_USER", ""))
    s3_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", os.getenv("MINIO_ROOT_PASSWORD", ""))
    s3_region: str = os.getenv("AWS_REGION", "us-east-1")
    ocr_provider: str = os.getenv("LIPIOCR_OCR_PROVIDER", "mock")
    gemma_api_base: str = os.getenv("LIPIOCR_GEMMA_API_BASE", "http://127.0.0.1:8003/v1")
    gemma_model: str = os.getenv("LIPIOCR_GEMMA_MODEL", "gemma-4-26b-4bit")
    gemma_enabled: bool = os.getenv("LIPIOCR_GEMMA_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    gemma_timeout_seconds: float = float(os.getenv("LIPIOCR_GEMMA_TIMEOUT_SECONDS", "45"))
    gemma_max_tokens: int = int(os.getenv("LIPIOCR_GEMMA_MAX_TOKENS", "1200"))
    gemma_retries: int = int(os.getenv("LIPIOCR_GEMMA_RETRIES", "2"))
    gemma_require_json: bool = os.getenv("LIPIOCR_GEMMA_REQUIRE_JSON", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    api_auth_enabled: bool = os.getenv("LIPIOCR_API_AUTH_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    api_keys: str = os.getenv("LIPIOCR_API_KEYS", "")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
