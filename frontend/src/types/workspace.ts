import type { TemplateDragMode } from "../lib/template-canvas.ts";

export const workspaceSections = [
  "command",
  "cases",
  "documents",
  "review",
  "verification",
  "templates",
  "integrations",
  "analytics",
  "admin",
] as const;

export type WorkspaceSection = (typeof workspaceSections)[number];

export const jobStatuses = ["queued", "processing", "completed", "failed", "retry_scheduled"] as const;

export type JobStatus = (typeof jobStatuses)[number];

export type ProcessingJob = {
  id: string;
  job_type: string;
  status: JobStatus;
  target_type: string;
  target_id: string;
  payload: Record<string, unknown>;
  attempts: number;
  max_attempts: number;
  error?: { code: string; message: string } | null;
  result?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  completed_at?: string | null;
};

export type JobEnvelope = {
  job_id: string;
  status: JobStatus;
  status_url: string;
};

export type CaseType = "individual_kyc" | "business_kyb" | "loan_onboarding" | "document_digitization";
export type CaseStatus = "created" | "processing" | "review_required" | "approved" | "rejected" | "exported";
export type DocumentType =
  | "unknown"
  | "citizenship"
  | "national_id"
  | "passport"
  | "driving_license"
  | "account_opening"
  | "ipo_application"
  | "asba_application"
  | "pan"
  | "vat"
  | "cheque"
  | "bank_statement"
  | "company_registration"
  | "board_resolution"
  | "tax_clearance";

export const documentAssetTypes = ["photo", "fingerprint", "signature", "stamp", "seal", "chip"] as const;

export type DocumentAssetType = (typeof documentAssetTypes)[number];

export const documentSectionSides = ["front", "back", "unknown"] as const;

export type DocumentSectionSide = (typeof documentSectionSides)[number];

export const addressCandidateSources = [
  "nepal_location_registry",
  "address_evidence_store",
  "fuzzy_alias_match",
  "reviewer_approved",
] as const;

export type AddressCandidateSource = (typeof addressCandidateSources)[number];

export type OcrBlock = {
  text: string;
  bbox: number[];
  confidence: number;
  block_type: string;
  language: string;
};

export type OcrPage = {
  page_number: number;
  width: number;
  height: number;
  blocks: OcrBlock[];
  image_uri?: string | null;
  ocr_confidence: number;
};

export type DocumentAsset = {
  id: string;
  asset_type: DocumentAssetType | string;
  label: string;
  page_number: number;
  bbox?: number[] | null;
  confidence: number;
  source: string;
  image_crop_uri?: string | null;
  review_status: string;
};

export type EvidenceLedgerEntry = {
  entry_id: string;
  page_number: number;
  block_index: number;
  text: string;
  normalized_text: string;
  language: string;
  block_type: string;
  confidence: number;
  bbox?: number[] | null;
  mapped_field_key?: string | null;
  asset_type?: string | null;
  section_id?: string | null;
  section_side?: DocumentSectionSide | string | null;
};

export type DocumentSection = {
  id: string;
  side: DocumentSectionSide | string;
  label: string;
  page_number: number;
  bbox?: number[] | null;
  confidence: number;
  source: string;
  signals: string[];
};

export type DocumentVariantMetadata = {
  key: string;
  label: string;
  document_type: DocumentType | string;
  version_family: string;
  confidence: number;
  reason: string;
  matched_signals: string[];
};

export type EntityRecord = {
  entity_key: string;
  canonical_key: string;
  original_ne?: string;
  original_en?: string;
  normalized_ne?: string;
  normalized_en?: string;
  value?: string;
  normalized_value?: string;
  source_fields: string[];
  confidence: number;
  status: string;
  audit_reason: string;
};

export type NameCorrectionCandidate = {
  canonical_key?: string;
  target_field?: string;
  source_field_used?: string;
  field_key?: string;
  original_value?: string;
  original_ocr_value?: string;
  suggested_value: string;
  confidence: number;
  status: string;
  sources: string[];
  audit_reason: string;
  candidate_tokens?: {
    original: string;
    suggested_roman: string;
    suggested_nepali: string;
    distance: number;
    frequency: number;
    sources: string[];
  }[];
};

export type AddressCandidate = {
  target_field: string;
  original_ocr_value: string;
  suggested_value: string;
  structured?: {
    province?: string;
    district?: string;
    local_level?: string;
    ward?: string;
    area_or_tole?: string;
    street_or_road?: string;
  };
  confidence: number;
  status: "suggested" | "needs_review";
  sources?: string[];
  score_breakdown?: Record<string, number>;
  audit_reason?: string;
};

export type LocationResolution = {
  field_prefix?: string;
  source_value?: string;
  raw_text: string;
  normalized_text: string;
  status: string;
  confidence: number;
  province_code?: string | null;
  province_name?: string | null;
  district_code?: string | null;
  district_name?: string | null;
  local_level_code?: string | null;
  local_level_name?: string | null;
  local_level_key?: string | null;
  local_level_type?: string | null;
  ward?: string | null;
  warnings: string[];
  reasons: string[];
};

export type PreviewOverlayMode = "clean" | "evidence" | "blocks";

export type FinancialDocument = {
  id: string;
  filename: string;
  declared_document_type: DocumentType;
  document_type: DocumentType;
  status: string;
  page_count: number;
  pages: OcrPage[];
  summary: string;
  document_variant?: string | null;
  assets?: DocumentAsset[];
  document_sections?: DocumentSection[];
  evidence_ledger?: EvidenceLedgerEntry[];
  intelligence?: DocumentIntelligence | null;
};

export type DocumentVersion = {
  version: number;
  action: string;
  filename: string;
  document_type: DocumentType;
  status: string;
  overall_confidence: number;
  fields_count: number;
  summary: string;
  actor: string;
  note: string;
  created_at: string;
};

export type DocumentRecord = {
  id: string;
  filename: string;
  declared_document_type: DocumentType;
  document_type: DocumentType;
  status: string;
  overall_confidence: number;
  pages: OcrPage[];
  fields: ExtractedField[];
  summary: string;
  document_variant?: string | null;
  assets?: DocumentAsset[];
  document_sections?: DocumentSection[];
  evidence_ledger?: EvidenceLedgerEntry[];
  intelligence?: DocumentIntelligence | null;
  validation_findings: ValidationFinding[];
  audit_events: AuditEvent[];
  version_history: DocumentVersion[];
  review: {
    reviewer?: string | null;
    note?: string | null;
    reviewed_at?: string | null;
  };
  created_at: string;
  updated_at?: string;
};

export type DocumentLane = "application" | "standalone";

export type ExtractedField = {
  key: string;
  label: string;
  value: string;
  confidence: number;
  required?: boolean;
  source?: string;
  validation_status: string;
  validation_message: string;
  evidence: {
    document_id?: string | null;
    source_page: number;
    bbox?: number[] | null;
    evidence_text: string;
  };
  extracted_by: string;
  review_status: string;
  document_id?: string | null;
  original_ocr_value?: string | null;
  corrected_value?: string | null;
  source_field_used?: string | null;
  correction_confidence?: number | null;
  audit_reason?: string | null;
  correction_candidates?: (NameCorrectionCandidate | AddressCandidate)[];
};

export type ValidationFinding = {
  severity: string;
  code: string;
  message: string;
  field_key?: string | null;
  document_id?: string | null;
};

export type AuditEvent = {
  action: string;
  actor: string;
  note: string;
  created_at: string;
};

export type KycCase = {
  id: string;
  case_type: CaseType;
  applicant_name: string;
  institution_id: string;
  branch_code?: string | null;
  integration_ref?: string | null;
  status: CaseStatus;
  risk_level: string;
  documents: FinancialDocument[];
  extracted_fields: ExtractedField[];
  validation_findings: ValidationFinding[];
  audit_events: AuditEvent[];
  review: {
    reviewer?: string | null;
    note?: string | null;
    reviewed_at?: string | null;
  };
  created_at: string;
  updated_at?: string;
};

export type AiHealth = {
  provider: string;
  model: string;
  api_base?: string;
  enabled: boolean;
};

export type ResourceState<T> = {
  status: "idle" | "loading" | "ready" | "error";
  data: T | null;
  error: string | null;
  updatedAt: string | null;
};

export type ChecklistItem = {
  key: string;
  label: string;
  category?: string;
  required?: boolean;
  satisfied?: boolean;
  status?: string;
  severity?: string;
  message?: string;
  confidence?: number;
};

export type DocumentIntelligence = {
  document_id: string;
  filename: string;
  document_type: DocumentType;
  declared_document_type: DocumentType;
  confidence: number;
  reason: string;
  document_variant?: DocumentVariantMetadata;
  document_sections?: DocumentSection[];
  canonical_fields: Record<string, string>;
  assets?: DocumentAsset[];
  evidence_ledger?: EvidenceLedgerEntry[];
  entity_records?: EntityRecord[];
  location_resolutions?: LocationResolution[];
  language_pairs: {
    canonical_key: string;
    nepali_field?: string;
    english_field?: string;
    nepali_value: string;
    english_value: string;
    nepali_normalized?: string;
    english_normalized?: string;
    status: string;
    message: string;
  }[];
  normalizations?: Record<
    string,
    {
      original_value: string;
      normalized_value: string;
      method: string;
      confidence: number;
      audit_reason: string;
    }
  >;
  confidence_repairs?: {
    canonical_key: string;
    target_field: string;
    source_field_used: string;
    original_ocr_value: string;
    corrected_value: string;
    original_confidence: number;
    confidence: number;
    status: string;
    audit_reason: string;
  }[];
  name_candidates?: NameCorrectionCandidate[];
  address_candidates?: AddressCandidate[];
  cross_checks: {
    key: string;
    status: string;
    severity: string;
    message: string;
  }[];
  review_recommendations: string[];
};

export type CaseIntelligence = {
  case_id: string;
  country: string;
  workflow: string;
  readiness_score: number;
  completeness_score: number;
  risk_score: number;
  summary: string;
  checklist: ChecklistItem[];
  policy_signals: ChecklistItem[];
  document_intelligence?: DocumentIntelligence[];
  canonical_fields?: Record<string, string>;
  language_pairs?: DocumentIntelligence["language_pairs"];
  confidence_repairs?: NonNullable<DocumentIntelligence["confidence_repairs"]>;
  entity_reconciliation?: {
    left_filename: string;
    right_filename: string;
    left_value: string;
    right_value: string;
    status: string;
    confidence: number;
    reason: string;
  }[];
  cross_checks?: DocumentIntelligence["cross_checks"];
  gaps: string[];
  next_actions: string[];
  recommended_action: string;
};

export type PacketDocument = {
  document_id?: string;
  id?: string;
  filename?: string;
  document_type?: string;
  declared_document_type?: string;
  predicted_type?: string;
  previous_type?: string;
  action?: string;
  confidence?: number;
  page_count?: number;
  reason?: string;
};

export type SplitPreviewResponse = {
  case_id: string;
  segments: PacketDocument[];
  documents: PacketDocument[];
  warnings: string[];
};

export type ClassificationResponse = {
  case_id: string;
  classifications: PacketDocument[];
  documents: PacketDocument[];
  summary: string;
  case?: KycCase;
};

export type ValidationResponse = {
  case_id: string;
  status: string;
  summary: {
    finding_count: number;
    blocking_issue_count: number;
    warning_count: number;
  };
  findings: ValidationFinding[];
  case?: KycCase;
};

export type VerificationCheck = {
  key: string;
  label: string;
  status: string;
  severity: string;
  message: string;
  next_step: string;
};

export type VerificationResponse = {
  case_id: string;
  run_id: string;
  status: string;
  decision: string;
  score: number;
  checks: VerificationCheck[];
  next_steps: string[];
  case?: KycCase;
};

export type IntegrationProfile = {
  key: string;
  name: string;
  category: string;
  mode: string;
  status: string;
  description: string;
};

export type IntegrationProfilesResponse = {
  product: string;
  country: string;
  profiles: IntegrationProfile[];
  export_profiles: string[];
  events: string[];
  security: Record<string, unknown>;
};

export type PlatformComponent = {
  key: string;
  label: string;
  status: string;
  detail: string;
  next_step: string;
};

export type PlatformStatus = {
  product: string;
  country: string;
  deployment_target: string;
  case_count: number;
  components: PlatformComponent[];
  next_actions: string[];
};

export type OperationsLane = {
  key: string;
  label: string;
  count: number;
  description: string;
  case_ids: string[];
};

export type OperationsDashboard = {
  counts: {
    total_cases: number;
    documents: number;
    review_required: number;
    approved: number;
    exceptions: number;
  };
  lanes: OperationsLane[];
  bottlenecks: { key: string; severity: string; message: string }[];
  branch_load: Record<string, number>;
  case_type_load: Record<string, number>;
  next_best_actions: string[];
};

export type OcrPipelineProfile = {
  active_provider: string;
  providers: { key: string; label: string; status: string; best_for: string }[];
  preprocessing_stages: { key: string; label: string; status: string }[];
  outputs: string[];
  production_requirements: string[];
};

export type TemplateStudio = {
  country: string;
  templates: {
    document_type: string;
    name: string;
    field_count: number;
    required_fields: string[];
    status: string;
    mode: string;
    source?: string;
    locked?: boolean;
    validation_rule_count?: number;
  }[];
  profiles?: {
    id: string;
    name: string;
    document_type: string;
    version: number;
    status: string;
    page_count: number;
    field_count: number;
    quality_score?: number;
    updated_at: string;
  }[];
  extraction_modes: string[];
  rules: string[];
};

export type TemplateProfilePage = {
  id: string;
  page_number: number;
  filename: string;
  stored_name?: string | null;
  image_uri?: string | null;
  width: number;
  height: number;
  ocr_confidence: number;
  blocks: OcrBlock[];
};

export type TemplateProfileField = {
  id: string;
  key: string;
  label: string;
  page_number: number;
  bbox: number[];
  type: string;
  required: boolean;
  language_hint: string;
  validation_rule?: string | null;
  extraction_hint: string;
  confidence: number;
  detection_source?: string;
  detection_reason?: string;
};

export type TemplateDraft = {
  id: string;
  name: string;
  document_type: DocumentType;
  status: string;
  document_type_confidence?: number;
  document_type_reason?: string;
  quality_score?: number;
  quality_checks?: { key: string; status: string; detail: string }[];
  pages: TemplateProfilePage[];
  fields: TemplateProfileField[];
  created_at: string;
  updated_at: string;
};

export type TemplateDragState = {
  fieldId: string;
  mode: TemplateDragMode;
  startBbox: number[];
  startClientX: number;
  startClientY: number;
};

export type WebhookTestResponse = {
  status: string;
  event_id: string;
  signature?: string;
};

export type EmbeddedReviewLinkResponse = {
  url: string;
  review_url: string;
  token: string;
  expires_at: string;
};

export type ExportProfileResponse = {
  case_id: string;
  profile_key: string;
  generated_at: string;
  payload: unknown;
};

export type ReviewAssignment = {
  reviewer: string;
  queue: string;
  priority: string;
  assigned_at?: string;
};

export type ReviewWorkbench = {
  case_id: string;
  assignment: ReviewAssignment;
  comments: {
    comment_id: string;
    author: string;
    message: string;
    field_key?: string | null;
    visibility: string;
    created_at: string;
  }[];
  rework_requests: {
    request_id: string;
    requester: string;
    reason: string;
    fields: string[];
    status: string;
    created_at: string;
  }[];
  field_corrections: Record<string, unknown>[];
  approval_history: {
    action: string;
    actor: string;
    note: string;
    created_at: string;
  }[];
  evidence_crops: {
    field_key: string;
    document_id?: string | null;
    source_page: number;
    bbox?: number[] | null;
    evidence_text: string;
    crop_uri: string;
  }[];
  editable_fields: ExtractedField[];
};

export type AssignmentResponse = {
  case_id: string;
  assignment: ReviewAssignment;
  case?: KycCase;
};

export type CommentResponse = {
  case_id: string;
  comment: ReviewWorkbench["comments"][number];
};

export type CorrectionResponse = {
  correction: Record<string, unknown>;
  case?: KycCase;
};

export type IntegrationOperations = {
  webhooks: {
    key: string;
    url: string;
    events: string[];
    status: string;
    created_at?: string;
  }[];
  retry_queue: {
    event_id: string;
    mode: string;
    profile_key?: string;
    target?: string;
    case_ids?: string[];
    status: string;
    attempts: number;
    last_error?: string;
  }[];
  dead_letters: Record<string, unknown>[];
  sftp: {
    status: string;
    pending_batches: number;
  };
};

export type VerificationAdapter = {
  key: string;
  label: string;
  status: string;
  mode: string;
  endpoint?: string;
  updated_at?: string;
};

export type VerificationAdaptersResponse = {
  adapters: VerificationAdapter[];
};

export type VerificationAdapterRunResponse = {
  case_id: string;
  adapter: VerificationAdapter;
  check: VerificationCheck;
  case?: KycCase;
};

export type FieldGroup = {
  key: string;
  label: string;
  description: string;
  fields: ExtractedField[];
};

export type AccuracyAnalytics = {
  correction_count: number;
  field_accuracy: Record<
    string,
    {
      corrections: number;
      observed: number;
      average_confidence: number;
      estimated_accuracy: number;
    }
  >;
  document_type_performance: Record<string, { corrections: number; status: string }>;
  benchmark?: {
    name?: string;
    version?: string;
    sample_count: number;
    overall: {
      character_error_rate: number;
      word_error_rate: number;
      field_precision: number;
      field_recall: number;
      field_f1: number;
      reviewer_correction_rate: number;
    };
    by_mode: Record<string, { field_f1: number; reviewer_correction_rate: number }>;
    by_language?: Record<string, { field_count: number; field_f1: number; reviewer_correction_rate: number }>;
    by_document_type?: Record<string, { field_f1: number; reviewer_correction_rate: number }>;
    by_field?: Record<
      string,
      {
        expected: number;
        extracted: number;
        matched: number;
        precision: number;
        recall: number;
        f1: number;
        average_character_error_rate: number;
        average_confidence: number;
        document_types: string[];
        modes: string[];
        languages: string[];
      }
    >;
    confidence_buckets?: Record<string, { field_count: number; matched: number; precision: number }>;
    handwriting?: {
      sample_count: number;
      field_count: number;
      nepali_field_count: number;
      weak_fields: { field_key: string; f1: number; recall: number; average_character_error_rate: number; expected: number }[];
    };
    weak_fields?: { field_key: string; f1: number; recall: number; average_character_error_rate: number; expected: number }[];
    dataset_readiness?: {
      document_type_count: number;
      handwriting_sample_count: number;
      nepali_field_count: number;
      status: string;
      gaps: string[];
    };
  };
  confidence_drift: {
    field_key: string;
    average_confidence: number;
    corrections: number;
  }[];
  recent_corrections: Record<string, unknown>[];
};
