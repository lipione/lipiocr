from typing import Dict, Optional

from fastapi import APIRouter, Request

from app.app_context import gemma_client, settings
from app.services.security import require_permission

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> Dict[str, str]:
    return {
        "status": "ok",
        "service": "lipiocr-enterprise",
        "environment": settings.environment,
    }


@router.get("/api/ai/health")
def ai_health(http_request: Request, detail: Optional[str] = None):
    if detail == "internal":
        require_permission(settings, http_request, "view_audit")
        return gemma_client().health(include_internal=True)
    return gemma_client().health(include_internal=False)
