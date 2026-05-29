from fastapi import APIRouter

router = APIRouter(tags=["integration-manifest"])


@router.get("/api/integrations/manifest")
def integration_manifest():
    return {
        "product": "LipiOCR Enterprise",
        "country": "Nepal",
        "modes": ["manual_export", "rest_api", "webhooks", "sftp", "embedded_review"],
        "events": [
            "case.created",
            "document.processed",
            "review.required",
            "case.approved",
            "case.rejected",
            "export.completed",
        ],
        "core_endpoints": [
            "POST /api/cases",
            "POST /api/cases/{case_id}/documents",
            "GET /api/cases/{case_id}/export",
        ],
    }
