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
  canonical_fields: Record<string, string>;
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
  }[];
  profiles?: {
    id: string;
    name: string;
    document_type: string;
    version: number;
    status: string;
    page_count: number;
    field_count: number;
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
};

export type TemplateDraft = {
  id: string;
  name: string;
  document_type: DocumentType;
  status: string;
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
  confidence_drift: {
    field_key: string;
    average_confidence: number;
    corrections: number;
  }[];
  recent_corrections: Record<string, unknown>[];
};
