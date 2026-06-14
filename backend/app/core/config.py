import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = "LipiOCR Enterprise"
    environment: str = os.getenv("LIPIOCR_ENVIRONMENT", "development")
    cors_origins: str = os.getenv("LIPIOCR_CORS_ORIGINS", "http://localhost:3000")
    upload_dir: Path = Path(os.getenv("LIPIOCR_UPLOAD_DIR", "storage/uploads"))
    repository_backend: str = os.getenv("LIPIOCR_REPOSITORY_BACKEND", "auto")
    database_url: str = os.getenv("DATABASE_URL", "")
    async_jobs_enabled: bool = os.getenv("LIPIOCR_ASYNC_JOBS_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    storage_backend: str = os.getenv("LIPIOCR_STORAGE_BACKEND", "auto")
    s3_endpoint_url: str = os.getenv("S3_ENDPOINT_URL", "")
    s3_bucket: str = os.getenv("S3_BUCKET", "lipiocr-documents")
    s3_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", os.getenv("MINIO_ROOT_USER", ""))
    s3_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", os.getenv("MINIO_ROOT_PASSWORD", ""))
    s3_region: str = os.getenv("AWS_REGION", "us-east-1")
    ocr_provider: str = os.getenv("LIPIOCR_OCR_PROVIDER", "mock")
    paddle_lang: str = os.getenv("LIPIOCR_PADDLE_LANG", "en")
    paddle_det_model_dir: str = os.getenv("LIPIOCR_PADDLE_DET_MODEL_DIR", "")
    paddle_rec_model_dir: str = os.getenv("LIPIOCR_PADDLE_REC_MODEL_DIR", "")
    paddle_cls_model_dir: str = os.getenv("LIPIOCR_PADDLE_CLS_MODEL_DIR", "")
    paddle_rec_char_dict_path: str = os.getenv("LIPIOCR_PADDLE_REC_CHAR_DICT_PATH", "")
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
    gemma_vision_tiling_enabled: bool = os.getenv("LIPIOCR_GEMMA_VISION_TILING_ENABLED", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    gemma_vision_tile_count: int = int(os.getenv("LIPIOCR_GEMMA_VISION_TILE_COUNT", "4"))
    gemma_vision_tile_overlap_px: int = int(os.getenv("LIPIOCR_GEMMA_VISION_TILE_OVERLAP_PX", "96"))
    gemma_vision_tile_min_lines: int = int(os.getenv("LIPIOCR_GEMMA_VISION_TILE_MIN_LINES", "8"))
    gemma_require_json: bool = os.getenv("LIPIOCR_GEMMA_REQUIRE_JSON", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    legacy_ocr_fallback_enabled: bool = os.getenv("LIPIOCR_LEGACY_OCR_FALLBACK_ENABLED", "true").lower() in {
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
    session_secret: str = os.getenv(
        "LIPIOCR_SESSION_SECRET",
        os.getenv("LIPIOCR_API_KEYS", "lipiocr-dev-session-secret"),
    )
    session_ttl_seconds: int = int(os.getenv("LIPIOCR_SESSION_TTL_SECONDS", "43200"))
    session_cookie_name: str = os.getenv("LIPIOCR_SESSION_COOKIE_NAME", "lipiocr_session")
    default_tenant_id: str = os.getenv("LIPIOCR_DEFAULT_TENANT_ID", "demo-institution")
    max_upload_bytes: int = int(os.getenv("LIPIOCR_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
    allowed_upload_mime_types: str = os.getenv(
        "LIPIOCR_ALLOWED_UPLOAD_MIME_TYPES",
        "application/pdf,image/avif,image/bmp,image/gif,image/jpeg,image/png,image/tiff,image/webp,text/plain",
    )
    allowed_upload_extensions: str = os.getenv(
        "LIPIOCR_ALLOWED_UPLOAD_EXTENSIONS",
        ".avif,.bmp,.gif,.jpeg,.jpg,.pdf,.png,.tif,.tiff,.txt,.webp",
    )
    preview_token_secret: str = os.getenv(
        "LIPIOCR_PREVIEW_TOKEN_SECRET",
        os.getenv("LIPIOCR_API_KEYS", "lipiocr-dev-preview-secret"),
    )
    preview_token_ttl_seconds: int = int(os.getenv("LIPIOCR_PREVIEW_TOKEN_TTL_SECONDS", "900"))
    benchmark_manifest_path: str = os.getenv("LIPIOCR_BENCHMARK_MANIFEST", "")
    nepali_name_lexicon_path: str = os.getenv(
        "LIPIOCR_NEPALI_NAME_LEXICON",
        "storage/name-lexicon/nepali_name_lexicon.json",
    )
    address_evidence_path: str = Field(
        default_factory=lambda: os.getenv(
            "LIPIOCR_ADDRESS_EVIDENCE_PATH",
            "storage/address-evidence/address_evidence.json",
        )
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
