from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.services.gemma import GemmaReasoningClient
from app.services.ocr import get_ocr_provider
from app.services.repository import repository
from app.services.storage import build_storage

settings = get_settings()
BASE_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = Path(settings.upload_dir)
if not UPLOAD_DIR.is_absolute():
    UPLOAD_DIR = BASE_DIR / UPLOAD_DIR
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
object_storage = build_storage(settings)


def gemma_client() -> GemmaReasoningClient:
    return GemmaReasoningClient(settings)


def ocr_provider(provider_name: Optional[str] = None):
    return get_ocr_provider(provider_name or settings.ocr_provider)
