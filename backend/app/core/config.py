import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "LipiOCR Enterprise"
    environment: str = os.getenv("LIPIOCR_ENVIRONMENT", "development")
    cors_origins: str = os.getenv("LIPIOCR_CORS_ORIGINS", "http://localhost:3000")
    upload_dir: Path = Path(os.getenv("LIPIOCR_UPLOAD_DIR", "storage/uploads"))
    gemma_api_base: str = os.getenv("LIPIOCR_GEMMA_API_BASE", "http://127.0.0.1:8003/v1")
    gemma_model: str = os.getenv("LIPIOCR_GEMMA_MODEL", "gemma-4-26b-4bit")
    gemma_enabled: bool = os.getenv("LIPIOCR_GEMMA_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    gemma_timeout_seconds: float = float(os.getenv("LIPIOCR_GEMMA_TIMEOUT_SECONDS", "45"))

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
