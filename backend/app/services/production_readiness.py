from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Iterable

from app.models import CaseStatus, KycCase
from app.services.integrations import list_integration_profiles
from app.services.templates import list_templates, list_validation_rules


def _component(key: str, label: str, status: str, detail: str, next_step: str) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "detail": detail,
        "next_step": next_step,
    }


def build_ocr_pipeline_profile(settings) -> dict[str, object]:
    active_provider = settings.ocr_provider
    providers = [
        {
            "key": "mock",
            "label": "LipiCore Demo",
            "status": "configured" if active_provider == "mock" else "available",
            "best_for": "Local demos and repeatable tests",
        },
        {
            "key": "tesseract",
            "label": "LipiCore Nepali OCR",
            "status": "configured" if active_provider == "tesseract" else "optional",
            "best_for": "Devanagari fallback and low-resource deployments",
        },
        {
            "key": "paddleocr",
            "label": "LipiCore Printed OCR",
            "status": "configured" if active_provider == "paddleocr" else "optional",
            "best_for": "Modern printed document OCR and layout-aware extraction",
        },
        {
            "key": "gemma_vision",
            "label": "LipiCore Vision",
            "status": "configured" if active_provider == "gemma_vision" else "available",
            "best_for": "Remote full-page Nepali/English OCR plus handwritten field transcription",
        },
    ]
    stages = [
        ("deskew", "Deskew scanned pages before OCR"),
        ("denoise", "Reduce speckle/noise from mobile scans and old photocopies"),
        ("rotation_detection", "Detect portrait/landscape and upside-down pages"),
        ("language_routing", "Route English, Nepali, and mixed text to the best provider"),
        ("confidence_calibration", "Normalize OCR and AI confidence into review thresholds"),
    ]
    return {
        "active_provider": active_provider,
        "environment": settings.environment,
        "providers": providers,
        "preprocessing_stages": [
            {
                "key": key,
                "label": label,
                "status": "configured" if key in {"deskew", "denoise", "rotation_detection"} else "planned",
            }
            for key, label in stages
        ],
        "outputs": ["ocr_pages", "text_blocks", "bounding_boxes", "confidence_scores"],
        "production_requirements": [
            "Install local fallback OCR in the deployment image",
            "Run representative Nepali financial documents through accuracy evaluation",
            "Calibrate confidence thresholds from reviewer corrections",
        ],
    }


def build_platform_status(settings, cases: Iterable[KycCase]) -> dict[str, object]:
    case_list = list(cases)
    database_url = settings.database_url
    storage_backend = settings.storage_backend
    if storage_backend == "auto":
        storage_backend = "s3" if settings.s3_endpoint_url else "local"
    repository_backend = settings.repository_backend
    if repository_backend == "auto":
        repository_backend = "sql" if settings.database_url else "memory"
    active_provider = settings.ocr_provider
    integration_profiles = list_integration_profiles()["profiles"]
    configured_integrations = sum(1 for profile in integration_profiles if profile["status"] == "configured")

    components = [
        _component(
            "ocr_pipeline",
            "OCR and preprocessing",
            "configured" if active_provider != "mock" else "partial",
            "Active provider configured",
            "Benchmark LipiCore recognition against Nepali KYC packets",
        ),
        _component(
            "gemma_brain",
            "LipiCore reasoning",
            "configured" if settings.gemma_enabled else "partial",
            "Secure reasoning service configured" if settings.gemma_enabled else "Reasoning service ready for production endpoint",
            "Enable the production reasoning endpoint and enforce structured JSON outputs",
        ),
        _component(
            "persistence",
            "Case persistence",
            "configured" if repository_backend == "sql" and database_url else "partial",
            "SQL repository active" if repository_backend == "sql" and database_url else "Local API uses in-memory repository",
            "Run SQL repository against managed PostgreSQL and add schema migrations",
        ),
        _component(
            "object_storage",
            "Document object storage",
            "configured" if storage_backend == "s3" else "partial",
            settings.s3_endpoint_url if storage_backend == "s3" else "Local upload/object store is active",
            "Use MinIO/S3 for source files, crops, and exports with retention policy",
        ),
        _component(
            "security",
            "Security and tenant controls",
            "configured" if settings.api_auth_enabled else "partial",
            "API-key RBAC enforcement enabled" if settings.api_auth_enabled else "API-key RBAC is available but disabled for local development",
            "Add OIDC/SSO and tenant identity provider integration after API-key pilot",
        ),
        _component(
            "integrations",
            "Institution integrations",
            "partial" if configured_integrations else "not_configured",
            f"{configured_integrations} integration profile(s) configured as local contracts",
            "Add institution-specific CBS/LOS/AML endpoints and retry/dead-letter handling",
        ),
    ]

    return {
        "product": "LipiOCR Enterprise",
        "country": "Nepal",
        "deployment_target": "on_prem_or_private_cloud",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "case_count": len(case_list),
        "components": components,
        "next_actions": [
            "Run PostgreSQL repository and MinIO-backed document storage in production compose",
            "Install production OCR providers and evaluate Nepali document accuracy",
            "Enable API-key or SSO enforcement before financial-institution pilot data",
            "Configure live registry, AML, liveness, and CBS/LOS adapters per institution",
        ],
    }


def _case_has_error(case: KycCase) -> bool:
    return any(finding.severity == "error" for finding in case.validation_findings)


def _lane(key: str, label: str, cases: list[KycCase], description: str) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "count": len(cases),
        "description": description,
        "case_ids": [case.id for case in cases[:8]],
    }


def build_operations_dashboard(cases: Iterable[KycCase]) -> dict[str, object]:
    case_list = sorted(list(cases), key=lambda item: item.updated_at, reverse=True)
    intake_cases = [case for case in case_list if case.status in {CaseStatus.created, CaseStatus.processing}]
    review_cases = [case for case in case_list if case.status == CaseStatus.review_required]
    exception_cases = [case for case in case_list if case.risk_level.value == "high" or _case_has_error(case)]
    export_cases = [case for case in case_list if case.status in {CaseStatus.approved, CaseStatus.exported}]
    verification_cases = [
        case
        for case in case_list
        if case.status == CaseStatus.review_required and any("verification" in event.action for event in case.audit_events)
    ]

    status_counts = Counter(case.status.value for case in case_list)
    branch_load: dict[str, int] = defaultdict(int)
    case_type_load = Counter(case.case_type.value for case in case_list)
    for case in case_list:
        branch_load[case.branch_code or "unassigned"] += 1

    bottlenecks = []
    if review_cases:
        bottlenecks.append(
            {
                "key": "review_queue",
                "severity": "warning",
                "message": f"{len(review_cases)} case(s) waiting for maker-checker review",
            }
        )
    if exception_cases:
        bottlenecks.append(
            {
                "key": "exceptions",
                "severity": "error",
                "message": f"{len(exception_cases)} case(s) have high-risk or blocking validation issues",
            }
        )
    if not case_list:
        bottlenecks.append(
            {
                "key": "no_cases",
                "severity": "info",
                "message": "No active cases in the operations queue",
            }
        )

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "counts": {
            "total_cases": len(case_list),
            "documents": sum(len(case.documents) for case in case_list),
            "review_required": status_counts.get("review_required", 0),
            "approved": status_counts.get("approved", 0),
            "exceptions": len(exception_cases),
        },
        "lanes": [
            _lane("intake", "Intake", intake_cases, "New uploads and OCR processing"),
            _lane("review", "Review", review_cases, "Maker-checker cases needing human decision"),
            _lane("verification", "Verification", verification_cases, "Cases with verification runs or adapter gaps"),
            _lane("exceptions", "Exceptions", exception_cases, "High-risk, missing, or inconsistent evidence"),
            _lane("export", "Export", export_cases, "Approved or exported cases ready for system handoff"),
        ],
        "bottlenecks": bottlenecks,
        "branch_load": dict(branch_load),
        "case_type_load": dict(case_type_load),
        "next_best_actions": [
            "Clear blocking validation issues before CBS export",
            "Prioritize high-risk or long-waiting review cases",
            "Configure missing external verification adapters by institution",
        ],
    }


def build_template_studio() -> dict[str, object]:
    from app.services.template_profiles import template_profile_summaries

    validation_rules = list_validation_rules()
    templates = []
    for template in list_templates():
        rule_count = len(validation_rules.get(template.document_type.value, []))
        templates.append(
            {
                "document_type": template.document_type.value,
                "name": template.name,
                "field_count": len(template.fields),
                "required_fields": [field.key for field in template.fields if field.required],
                "status": "configured",
                "mode": "template_coordinates",
                "validation_rule_count": rule_count,
            }
        )

    configured = {template["document_type"] for template in templates}
    for document_type, label in [
        ("national_id", "National ID"),
        ("pan", "PAN Certificate"),
        ("company_registration", "Company Registration"),
        ("board_resolution", "Board Resolution"),
        ("bank_statement", "Bank Statement"),
    ]:
        if document_type not in configured:
            templates.append(
                {
                    "document_type": document_type,
                    "name": label,
                    "field_count": 0,
                    "required_fields": [],
                    "status": "planned",
                    "mode": "full_page_reasoning",
                    "validation_rule_count": 0,
                }
            )

    return {
        "country": "Nepal",
        "templates": templates,
        "profiles": template_profile_summaries(),
        "extraction_modes": ["template_coordinates", "full_page_reasoning", "human_review"],
        "rules": [
            "Template coordinates are preferred for stable bank forms",
            "Full-page reasoning handles mixed packets and unknown layouts",
            "Human review remains mandatory for uncertain or regulated fields",
        ],
        "validation_rules": validation_rules,
    }
