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
  ocr_confidence: number;
};

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

export type ExtractedField = {
  key: string;
  label: string;
  value: string;
  confidence: number;
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
  api_base: string;
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
  extraction_modes: string[];
  rules: string[];
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
