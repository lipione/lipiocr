from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


class CaseType(str, Enum):
    individual_kyc = "individual_kyc"
    business_kyb = "business_kyb"
    loan_onboarding = "loan_onboarding"
    document_digitization = "document_digitization"


class CaseStatus(str, Enum):
    created = "created"
    processing = "processing"
    review_required = "review_required"
    approved = "approved"
    rejected = "rejected"
    exported = "exported"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class DocumentType(str, Enum):
    unknown = "unknown"
    citizenship = "citizenship"
    national_id = "national_id"
    passport = "passport"
    driving_license = "driving_license"
    account_opening = "account_opening"
    ipo_application = "ipo_application"
    asba_application = "asba_application"
    pan = "pan"
    vat = "vat"
    cheque = "cheque"
    bank_statement = "bank_statement"
    company_registration = "company_registration"
    board_resolution = "board_resolution"
    tax_clearance = "tax_clearance"


class DocumentStatus(str, Enum):
    uploaded = "uploaded"
    processed = "processed"
    auto_approved = "auto_approved"
    review_required = "review_required"
    manual_entry = "manual_entry"
    approved = "approved"
    rejected = "rejected"


class ValidationStatus(str, Enum):
    valid = "valid"
    invalid = "invalid"
    missing = "missing"
    warning = "warning"


class ReviewStatus(str, Enum):
    pending = "pending"
    needs_review = "needs_review"
    verified = "verified"
    rejected = "rejected"


class AuditEvent(BaseModel):
    action: str
    actor: str = "system"
    note: str = ""
    metadata: Dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EvidenceRef(BaseModel):
    document_id: Optional[str] = None
    source_page: int = 1
    bbox: Optional[List[int]] = None
    evidence_text: str = ""
    image_crop_uri: Optional[str] = None


class OcrBlock(BaseModel):
    text: str
    bbox: List[int]
    confidence: float
    block_type: str = "text"
    language: str = "mixed"


class OcrPage(BaseModel):
    page_number: int
    width: int
    height: int
    blocks: List[OcrBlock] = Field(default_factory=list)
    image_uri: Optional[str] = None
    ocr_confidence: float = 0.0


class ExtractedField(BaseModel):
    key: str
    label: str
    value: str = ""
    confidence: float = 0.0
    required: bool = True
    source: str = "ai_reasoning"
    validation_status: ValidationStatus = ValidationStatus.warning
    validation_message: str = "Not validated"
    bbox: Optional[List[int]] = None
    evidence: EvidenceRef = Field(default_factory=EvidenceRef)
    extracted_by: str = "deterministic-fallback"
    review_status: ReviewStatus = ReviewStatus.needs_review
    document_id: Optional[str] = None


class ValidationFinding(BaseModel):
    severity: str
    code: str
    message: str
    field_key: Optional[str] = None
    document_id: Optional[str] = None


class FinancialDocument(BaseModel):
    id: str = Field(default_factory=lambda: new_id("doc"))
    filename: str
    declared_document_type: DocumentType = DocumentType.unknown
    document_type: DocumentType = DocumentType.unknown
    status: DocumentStatus = DocumentStatus.uploaded
    page_count: int = 0
    pages: List[OcrPage] = Field(default_factory=list)
    summary: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewState(BaseModel):
    reviewer: Optional[str] = None
    note: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class IntegrationEvent(BaseModel):
    mode: str
    status: str
    target: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class KycCase(BaseModel):
    id: str = Field(default_factory=lambda: new_id("case"))
    case_type: CaseType
    applicant_name: str
    institution_id: str = "demo-institution"
    branch_code: Optional[str] = None
    integration_ref: Optional[str] = None
    status: CaseStatus = CaseStatus.created
    risk_level: RiskLevel = RiskLevel.medium
    documents: List[FinancialDocument] = Field(default_factory=list)
    extracted_fields: List[ExtractedField] = Field(default_factory=list)
    validation_findings: List[ValidationFinding] = Field(default_factory=list)
    review: ReviewState = Field(default_factory=ReviewState)
    audit_events: List[AuditEvent] = Field(default_factory=list)
    integration_events: List[IntegrationEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CaseCreateRequest(BaseModel):
    case_type: CaseType = CaseType.individual_kyc
    applicant_name: str
    customer_ref: Optional[str] = None
    institution_id: str = "demo-institution"
    branch_code: Optional[str] = None


class ReviewRequest(BaseModel):
    reviewer: str
    field_updates: Dict[str, str] = Field(default_factory=dict)
    decision: str
    note: str = ""


class TemplateField(BaseModel):
    key: str
    label: str
    required: bool
    bbox: List[int]


class DocumentTemplate(BaseModel):
    document_type: DocumentType
    name: str
    fields: List[TemplateField]


class DocumentRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    filename: str
    document_type: DocumentType
    status: DocumentStatus
    overall_confidence: float
    fields: List[ExtractedField]
    audit_events: List[AuditEvent] = Field(default_factory=list)
    review: ReviewState = Field(default_factory=ReviewState)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
