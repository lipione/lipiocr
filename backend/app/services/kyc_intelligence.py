from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Iterable

from app.models import AuditEvent, CaseType, DocumentType, KycCase, ValidationFinding


CHECKLISTS: dict[CaseType, list[dict[str, object]]] = {
    CaseType.individual_kyc: [
        {
            "key": "citizenship",
            "label": "Citizenship or National ID evidence",
            "category": "identity",
            "required": True,
            "accepted_types": [
                DocumentType.citizenship,
                DocumentType.national_id,
                DocumentType.passport,
                DocumentType.driving_license,
            ],
        },
        {
            "key": "pan",
            "label": "PAN for tax and high-value product readiness",
            "category": "tax",
            "required": True,
            "accepted_types": [DocumentType.pan],
        },
        {
            "key": "account_opening",
            "label": "Signed account opening or KYC form",
            "category": "onboarding",
            "required": True,
            "accepted_types": [DocumentType.account_opening],
        },
        {
            "key": "photo_or_signature",
            "label": "Photo/signature evidence on source packet",
            "category": "biometric_evidence",
            "required": True,
            "accepted_types": [],
            "signal": "photo_or_signature",
        },
    ],
    CaseType.business_kyb: [
        {
            "key": "company_registration",
            "label": "Company registration certificate",
            "category": "entity_identity",
            "required": True,
            "accepted_types": [DocumentType.company_registration],
        },
        {
            "key": "pan_or_vat",
            "label": "Business PAN/VAT certificate",
            "category": "tax",
            "required": True,
            "accepted_types": [DocumentType.pan, DocumentType.vat],
        },
        {
            "key": "board_resolution",
            "label": "Board resolution or authorized signatory mandate",
            "category": "authority",
            "required": True,
            "accepted_types": [DocumentType.board_resolution],
        },
        {
            "key": "beneficial_owner_kyc",
            "label": "Beneficial owner KYC packet",
            "category": "ubo",
            "required": True,
            "accepted_types": [
                DocumentType.citizenship,
                DocumentType.national_id,
                DocumentType.passport,
            ],
        },
    ],
    CaseType.loan_onboarding: [
        {
            "key": "identity",
            "label": "Borrower identity evidence",
            "category": "identity",
            "required": True,
            "accepted_types": [
                DocumentType.citizenship,
                DocumentType.national_id,
                DocumentType.passport,
                DocumentType.driving_license,
            ],
        },
        {
            "key": "pan",
            "label": "PAN for borrower tax profile",
            "category": "tax",
            "required": True,
            "accepted_types": [DocumentType.pan],
        },
        {
            "key": "bank_statement",
            "label": "Bank statement or income evidence",
            "category": "income",
            "required": True,
            "accepted_types": [DocumentType.bank_statement],
        },
        {
            "key": "signed_application",
            "label": "Signed loan application form",
            "category": "onboarding",
            "required": True,
            "accepted_types": [DocumentType.account_opening],
        },
    ],
    CaseType.document_digitization: [
        {
            "key": "classified_document",
            "label": "Document packet classified",
            "category": "digitization",
            "required": True,
            "accepted_types": [
                DocumentType.citizenship,
                DocumentType.national_id,
                DocumentType.passport,
                DocumentType.account_opening,
                DocumentType.pan,
                DocumentType.vat,
                DocumentType.cheque,
                DocumentType.bank_statement,
                DocumentType.company_registration,
                DocumentType.board_resolution,
                DocumentType.tax_clearance,
            ],
        },
        {
            "key": "text_layer",
            "label": "OCR text layer created",
            "category": "ocr",
            "required": True,
            "accepted_types": [],
            "signal": "has_ocr_text",
        },
        {
            "key": "review_ready",
            "label": "Ready for maker review",
            "category": "workflow",
            "required": True,
            "accepted_types": [],
            "signal": "has_document",
        },
    ],
}


KEYWORDS: dict[DocumentType, tuple[str, ...]] = {
    DocumentType.citizenship: ("citizenship", "citizenship no", "district", "government of nepal", "nagrita"),
    DocumentType.national_id: ("national id", "national identity", "nid"),
    DocumentType.passport: ("passport", "mrp", "travel document"),
    DocumentType.driving_license: ("driving licence", "driving license", "license no"),
    DocumentType.account_opening: ("account opening", "account type", "nominee", "customer declaration", "kyc form"),
    DocumentType.pan: ("pan", "permanent account number", "taxpayer"),
    DocumentType.vat: ("vat", "value added tax"),
    DocumentType.cheque: ("cheque", "payee", "rupees", "account payee", "check no"),
    DocumentType.bank_statement: ("statement", "debit", "credit", "balance", "transaction"),
    DocumentType.company_registration: ("company", "registration", "office of company registrar", "pvt", "limited"),
    DocumentType.board_resolution: ("board resolution", "resolved that", "authorized signatory", "minute"),
    DocumentType.tax_clearance: ("tax clearance", "clearance certificate", "ird"),
}


def _all_text(case: KycCase) -> str:
    return "\n".join(
        block.text
        for document in case.documents
        for page in document.pages
        for block in page.blocks
        if block.text
    )


def _document_text(document) -> str:
    return "\n".join(block.text for page in document.pages for block in page.blocks if block.text)


def _has_signal(case: KycCase, signal: str) -> bool:
    text = _all_text(case).lower()
    if signal == "photo_or_signature":
        return any(word in text for word in ("photo", "photograph", "signature", "thumbprint", "fingerprint"))
    if signal == "has_ocr_text":
        return bool(text.strip())
    if signal == "has_document":
        return bool(case.documents)
    return False


def _matching_documents(case: KycCase, item: dict[str, object]) -> list[dict[str, str]]:
    accepted_types = set(item.get("accepted_types", []))
    matches = [
        {
            "document_id": document.id,
            "filename": document.filename,
            "document_type": document.document_type.value,
        }
        for document in case.documents
        if document.document_type in accepted_types or document.declared_document_type in accepted_types
    ]
    signal = item.get("signal")
    if not matches and isinstance(signal, str) and _has_signal(case, signal):
        matches.append({"document_id": "packet_signal", "filename": "OCR packet", "document_type": signal})
    return matches


def build_checklist(case: KycCase) -> list[dict[str, object]]:
    items = []
    for item in CHECKLISTS.get(case.case_type, CHECKLISTS[CaseType.individual_kyc]):
        matches = _matching_documents(case, item)
        satisfied = bool(matches)
        items.append(
            {
                "key": item["key"],
                "label": item["label"],
                "category": item["category"],
                "required": item["required"],
                "satisfied": satisfied,
                "status": "passed" if satisfied else "missing",
                "severity": "info" if satisfied else ("error" if item["required"] else "warning"),
                "message": "Evidence present" if satisfied else "Required evidence not found in uploaded packet",
                "matched_documents": matches,
                "confidence": 0.96 if satisfied else 0.0,
            }
        )
    return items


def _readiness_score(checklist: Iterable[dict[str, object]]) -> int:
    required = [item for item in checklist if item.get("required")]
    if not required:
        return 100
    passed = sum(1 for item in required if item.get("satisfied"))
    return round((passed / len(required)) * 100)


def build_case_intelligence(case: KycCase) -> dict[str, object]:
    checklist = build_checklist(case)
    readiness_score = _readiness_score(checklist)
    gaps = [item["key"] for item in checklist if item.get("required") and not item.get("satisfied")]
    if readiness_score == 100:
        action = "ready for checker review and export"
    elif case.documents:
        action = "review required: collect missing evidence and resolve validation gaps"
    else:
        action = "upload document packet for OCR and KYC extraction"

    return {
        "case_id": case.id,
        "country": "Nepal",
        "workflow": case.case_type.value,
        "readiness_score": readiness_score,
        "completeness_score": readiness_score,
        "risk_score": {"low": 25, "medium": 55, "high": 85}.get(case.risk_level.value, 55),
        "summary": f"{case.applicant_name} has {readiness_score}% required KYC packet readiness.",
        "checklist": checklist,
        "policy_signals": [
            {
                "key": "maker_checker",
                "label": "Maker-checker review",
                "status": "required",
                "severity": "warning",
                "message": "Nepal financial-institution deployments should keep human review before CBS export.",
            },
            {
                "key": "adapter_boundary",
                "label": "External registry checks",
                "status": "not_configured",
                "severity": "warning",
                "message": "National ID, PAN, AML, and liveness adapters require institution credentials.",
            },
        ],
        "gaps": gaps,
        "next_actions": [
            "Run document classification on the uploaded packet",
            "Resolve missing checklist evidence",
            "Run advanced verification adapters before approval",
        ],
        "recommended_action": action,
    }


def infer_document_type(document) -> tuple[DocumentType, float, str]:
    if document.declared_document_type != DocumentType.unknown:
        return document.declared_document_type, 0.91, "declared document type supplied by uploader"

    text = _document_text(document).lower()
    scores: Counter[DocumentType] = Counter()
    for document_type, keywords in KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                scores[document_type] += 1

    if not scores:
        return DocumentType.unknown, 0.35, "no strong OCR keywords matched"

    predicted, score = scores.most_common(1)[0]
    confidence = min(0.95, 0.62 + score * 0.11)
    return predicted, round(confidence, 2), f"matched {score} OCR keyword signal(s)"


def build_split_preview(case: KycCase) -> dict[str, object]:
    segments = []
    for index, document in enumerate(case.documents, start=1):
        predicted, confidence, reason = infer_document_type(document)
        page_count = document.page_count or len(document.pages) or 1
        segments.append(
            {
                "segment_id": f"seg_{index:03d}",
                "document_id": document.id,
                "filename": document.filename,
                "document_type": predicted.value,
                "declared_document_type": document.declared_document_type.value,
                "page_start": 1,
                "page_end": page_count,
                "pages": list(range(1, page_count + 1)),
                "page_count": page_count,
                "confidence": confidence,
                "reason": reason,
            }
        )

    return {
        "case_id": case.id,
        "packet_id": f"packet_{case.id}",
        "segments": segments,
        "documents": segments,
        "warnings": [] if segments else ["No documents uploaded yet"],
    }


def classify_case_documents(case: KycCase) -> dict[str, object]:
    classifications = []
    for document in case.documents:
        predicted, confidence, reason = infer_document_type(document)
        previous_type = document.document_type
        action = "kept"
        if predicted != DocumentType.unknown and predicted != document.document_type:
            document.document_type = predicted
            action = "updated"
        document.updated_at = datetime.utcnow()
        classifications.append(
            {
                "document_id": document.id,
                "filename": document.filename,
                "previous_type": previous_type.value,
                "predicted_type": predicted.value,
                "document_type": document.document_type.value,
                "declared_document_type": document.declared_document_type.value,
                "confidence": confidence,
                "reason": reason,
                "action": action,
            }
        )

    case.audit_events.append(
        AuditEvent(
            action="documents_classified",
            actor="kyc-intelligence",
            note=f"Classified {len(classifications)} document(s)",
        )
    )
    return {
        "case_id": case.id,
        "classifications": classifications,
        "documents": classifications,
        "summary": f"{len(classifications)} document(s) classified for {case.case_type.value}.",
        "case": case,
    }


def validate_case_consistency(case: KycCase) -> dict[str, object]:
    checklist = build_checklist(case)
    findings: list[ValidationFinding] = []
    for item in checklist:
        if item.get("required") and not item.get("satisfied"):
            findings.append(
                ValidationFinding(
                    severity="error",
                    code="required_document_missing",
                    message=f"{item['label']} is missing for {case.case_type.value}.",
                    field_key=str(item["key"]),
                )
            )

    field_values: dict[str, set[str]] = {}
    for field in case.extracted_fields:
        if field.value:
            field_values.setdefault(field.key, set()).add(field.value.strip().lower())
    for key, values in field_values.items():
        if len(values) > 1:
            findings.append(
                ValidationFinding(
                    severity="warning",
                    code="cross_document_mismatch",
                    message=f"{key} has conflicting values across source documents.",
                    field_key=key,
                )
            )

    if not case.extracted_fields:
        findings.append(
            ValidationFinding(
                severity="warning",
                code="no_fields_extracted",
                message="No structured fields have been extracted from this packet yet.",
            )
        )

    if not findings:
        findings.append(
            ValidationFinding(
                severity="info",
                code="ready_for_auto_approval",
                message="No blocking checklist or consistency issues detected; checker review is still recommended.",
            )
        )

    existing = {(finding.code, finding.field_key, finding.document_id) for finding in case.validation_findings}
    for finding in findings:
        identity = (finding.code, finding.field_key, finding.document_id)
        if identity not in existing:
            case.validation_findings.append(finding)

    blocking = sum(1 for finding in findings if finding.severity == "error")
    case.audit_events.append(
        AuditEvent(
            action="case_validated",
            actor="kyc-intelligence",
            note=f"{blocking} blocking issue(s) found",
        )
    )
    return {
        "case_id": case.id,
        "status": "blocked" if blocking else "review_ready",
        "summary": {
            "finding_count": len(findings),
            "blocking_issue_count": blocking,
            "warning_count": sum(1 for finding in findings if finding.severity == "warning"),
        },
        "findings": findings,
        "checklist": checklist,
        "case": case,
    }
