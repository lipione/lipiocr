"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  BadgeCheck,
  Boxes,
  BrainCircuit,
  ClipboardCheck,
  Database,
  Download,
  Eye,
  FileCog,
  FileSearch,
  FileText,
  Fingerprint,
  Gauge,
  History,
  Layers3,
  Link2,
  Loader2,
  LockKeyhole,
  Network,
  Play,
  Plug,
  Plus,
  RefreshCcw,
  Route,
  SearchCheck,
  ShieldAlert,
  ShieldCheck,
  SplitSquareHorizontal,
  Upload,
  Workflow,
} from "lucide-react";
import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from "react";

export type WorkspaceSection =
  | "command"
  | "cases"
  | "documents"
  | "review"
  | "verification"
  | "templates"
  | "integrations"
  | "analytics"
  | "admin";

type CaseType = "individual_kyc" | "business_kyb" | "loan_onboarding" | "document_digitization";
type CaseStatus = "created" | "processing" | "review_required" | "approved" | "rejected" | "exported";
type DocumentType =
  | "unknown"
  | "citizenship"
  | "national_id"
  | "passport"
  | "driving_license"
  | "account_opening"
  | "pan"
  | "vat"
  | "cheque"
  | "bank_statement"
  | "company_registration"
  | "board_resolution"
  | "tax_clearance";

type OcrBlock = {
  text: string;
  bbox: number[];
  confidence: number;
  block_type: string;
  language: string;
};

type OcrPage = {
  page_number: number;
  width: number;
  height: number;
  blocks: OcrBlock[];
  ocr_confidence: number;
};

type FinancialDocument = {
  id: string;
  filename: string;
  declared_document_type: DocumentType;
  document_type: DocumentType;
  status: string;
  page_count: number;
  pages: OcrPage[];
  summary: string;
};

type ExtractedField = {
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

type ValidationFinding = {
  severity: string;
  code: string;
  message: string;
  field_key?: string | null;
  document_id?: string | null;
};

type AuditEvent = {
  action: string;
  actor: string;
  note: string;
  created_at: string;
};

type KycCase = {
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

type AiHealth = {
  provider: string;
  model: string;
  api_base: string;
  enabled: boolean;
};

type ResourceState<T> = {
  status: "idle" | "loading" | "ready" | "error";
  data: T | null;
  error: string | null;
  updatedAt: string | null;
};

type ChecklistItem = {
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

type CaseIntelligence = {
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

type PacketDocument = {
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

type SplitPreviewResponse = {
  case_id: string;
  segments: PacketDocument[];
  documents: PacketDocument[];
  warnings: string[];
};

type ClassificationResponse = {
  case_id: string;
  classifications: PacketDocument[];
  documents: PacketDocument[];
  summary: string;
  case?: KycCase;
};

type ValidationResponse = {
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

type VerificationCheck = {
  key: string;
  label: string;
  status: string;
  severity: string;
  message: string;
  next_step: string;
};

type VerificationResponse = {
  case_id: string;
  run_id: string;
  status: string;
  decision: string;
  score: number;
  checks: VerificationCheck[];
  next_steps: string[];
  case?: KycCase;
};

type IntegrationProfile = {
  key: string;
  name: string;
  category: string;
  mode: string;
  status: string;
  description: string;
};

type IntegrationProfilesResponse = {
  product: string;
  country: string;
  profiles: IntegrationProfile[];
  export_profiles: string[];
  events: string[];
  security: Record<string, unknown>;
};

type PlatformComponent = {
  key: string;
  label: string;
  status: string;
  detail: string;
  next_step: string;
};

type PlatformStatus = {
  product: string;
  country: string;
  deployment_target: string;
  case_count: number;
  components: PlatformComponent[];
  next_actions: string[];
};

type OperationsLane = {
  key: string;
  label: string;
  count: number;
  description: string;
  case_ids: string[];
};

type OperationsDashboard = {
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

type OcrPipelineProfile = {
  active_provider: string;
  providers: { key: string; label: string; status: string; best_for: string }[];
  preprocessing_stages: { key: string; label: string; status: string }[];
  outputs: string[];
  production_requirements: string[];
};

type TemplateStudio = {
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

type WebhookTestResponse = {
  status: string;
  event_id: string;
  signature?: string;
};

type EmbeddedReviewLinkResponse = {
  url: string;
  review_url: string;
  token: string;
  expires_at: string;
};

type ExportProfileResponse = {
  case_id: string;
  profile_key: string;
  generated_at: string;
  payload: unknown;
};

type ReviewAssignment = {
  reviewer: string;
  queue: string;
  priority: string;
  assigned_at?: string;
};

type ReviewWorkbench = {
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

type AssignmentResponse = {
  case_id: string;
  assignment: ReviewAssignment;
  case?: KycCase;
};

type CommentResponse = {
  case_id: string;
  comment: ReviewWorkbench["comments"][number];
};

type CorrectionResponse = {
  correction: Record<string, unknown>;
  case?: KycCase;
};

type IntegrationOperations = {
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

type VerificationAdapter = {
  key: string;
  label: string;
  status: string;
  mode: string;
  endpoint?: string;
  updated_at?: string;
};

type VerificationAdaptersResponse = {
  adapters: VerificationAdapter[];
};

type VerificationAdapterRunResponse = {
  case_id: string;
  adapter: VerificationAdapter;
  check: VerificationCheck;
  case?: KycCase;
};

type AccuracyAnalytics = {
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

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8010";

const caseTypes: { value: CaseType; label: string }[] = [
  { value: "individual_kyc", label: "Individual KYC" },
  { value: "business_kyb", label: "Business KYB" },
  { value: "loan_onboarding", label: "Loan Onboarding" },
  { value: "document_digitization", label: "Digitization" },
];

const documentTypes: { value: DocumentType; label: string }[] = [
  { value: "citizenship", label: "Citizenship" },
  { value: "national_id", label: "National ID" },
  { value: "account_opening", label: "Account Form" },
  { value: "pan", label: "PAN/VAT" },
  { value: "cheque", label: "Cheque" },
  { value: "bank_statement", label: "Bank Statement" },
  { value: "company_registration", label: "Company Registration" },
  { value: "board_resolution", label: "Board Resolution" },
  { value: "unknown", label: "Unknown" },
];

const workspaceNav: { section: WorkspaceSection; href: string; label: string; description: string; icon: ReactNode }[] = [
  {
    section: "command",
    href: "/",
    label: "Command",
    description: "Portfolio workload, readiness, SLA pressure",
    icon: <Gauge size={16} />,
  },
  {
    section: "cases",
    href: "/cases",
    label: "Cases",
    description: "KYC/KYB case management and case detail",
    icon: <Boxes size={16} />,
  },
  {
    section: "documents",
    href: "/documents",
    label: "Documents",
    description: "Packet intake, OCR evidence, classification",
    icon: <FileSearch size={16} />,
  },
  {
    section: "review",
    href: "/review",
    label: "Review",
    description: "Maker-checker workbench and corrections",
    icon: <ClipboardCheck size={16} />,
  },
  {
    section: "verification",
    href: "/verification",
    label: "Verification",
    description: "Registry, AML, liveness and adapter checks",
    icon: <LockKeyhole size={16} />,
  },
  {
    section: "templates",
    href: "/templates",
    label: "Templates",
    description: "Template studio and validation rules",
    icon: <FileCog size={16} />,
  },
  {
    section: "integrations",
    href: "/integrations",
    label: "Integrations",
    description: "CBS, LOS, CRM, webhooks, SFTP, retry queue",
    icon: <Plug size={16} />,
  },
  {
    section: "analytics",
    href: "/analytics",
    label: "Analytics",
    description: "Accuracy, corrections, drift, throughput",
    icon: <Activity size={16} />,
  },
  {
    section: "admin",
    href: "/admin",
    label: "Admin",
    description: "Security, audit, tenant and deployment posture",
    icon: <ShieldCheck size={16} />,
  },
];

function emptyResource<T>(): ResourceState<T> {
  return { status: "idle", data: null, error: null, updatedAt: null };
}

function loadingResource<T>(current: ResourceState<T>): ResourceState<T> {
  return { ...current, status: "loading", error: null };
}

function readyResource<T>(data: T): ResourceState<T> {
  return { status: "ready", data, error: null, updatedAt: new Date().toISOString() };
}

function failedResource<T>(current: ResourceState<T>, error: unknown, fallback: string): ResourceState<T> {
  return {
    ...current,
    status: "error",
    error: error instanceof Error ? error.message : fallback,
    updatedAt: new Date().toISOString(),
  };
}

function labelize(value?: string) {
  return (value ?? "unknown").replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

function compactId(value?: string | null) {
  if (!value) {
    return "none";
  }
  return value.length > 20 ? `${value.slice(0, 9)}...${value.slice(-7)}` : value;
}

function pct(value?: number) {
  if (typeof value !== "number") {
    return "n/a";
  }
  return value <= 1 ? `${Math.round(value * 100)}%` : `${Math.round(value)}%`;
}

function formatDate(value?: string | null) {
  if (!value) {
    return "none";
  }
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function statusTone(status?: string) {
  const value = (status ?? "unknown").toLowerCase();
  if (["approved", "configured", "passed", "clean", "ready", "verified"].includes(value)) {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (["partial", "warning", "review_required", "needs_review", "missing", "not_configured"].includes(value)) {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  if (["error", "failed", "rejected", "blocked", "high"].includes(value)) {
    return "border-rose-200 bg-rose-50 text-rose-700";
  }
  if (["processing", "loading", "running"].includes(value)) {
    return "border-indigo-200 bg-indigo-50 text-indigo-700";
  }
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function blockStyle(block: OcrBlock, page: OcrPage) {
  const [x1, y1, x2, y2] = block.bbox;
  return {
    left: `${6 + (x1 / page.width) * 88}%`,
    top: `${22 + (y1 / page.height) * 72}%`,
    width: `${((x2 - x1) / page.width) * 88}%`,
    height: `${((y2 - y1) / page.height) * 72}%`,
  };
}

function packetDocuments(data: SplitPreviewResponse | ClassificationResponse | null) {
  if (!data) {
    return [];
  }
  return "segments" in data ? data.segments : data.classifications;
}

function isKycCase(value: unknown): value is KycCase {
  return Boolean(
    value &&
      typeof value === "object" &&
      "id" in value &&
      "case_type" in value &&
      "documents" in value &&
      "extracted_fields" in value,
  );
}

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(detail ? `${response.status} ${detail.slice(0, 160)}` : `${response.status}`);
  }
  return (await response.json()) as T;
}

export function EnterpriseWorkspace({ section }: { section: WorkspaceSection }) {
  const pathname = usePathname();
  const [cases, setCases] = useState<KycCase[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [caseType, setCaseType] = useState<CaseType>("individual_kyc");
  const [applicantName, setApplicantName] = useState("Sita Sharma");
  const [customerRef, setCustomerRef] = useState("CBS-1001");
  const [documentType, setDocumentType] = useState<DocumentType>("citizenship");
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("Starting");
  const [busy, setBusy] = useState(false);
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [exportJson, setExportJson] = useState("");
  const [profileKey, setProfileKey] = useState("cbs_standard");
  const [aiHealth, setAiHealth] = useState<ResourceState<AiHealth>>(() => emptyResource<AiHealth>());
  const [platform, setPlatform] = useState<ResourceState<PlatformStatus>>(() => emptyResource<PlatformStatus>());
  const [operations, setOperations] = useState<ResourceState<OperationsDashboard>>(() =>
    emptyResource<OperationsDashboard>(),
  );
  const [ocrPipeline, setOcrPipeline] = useState<ResourceState<OcrPipelineProfile>>(() =>
    emptyResource<OcrPipelineProfile>(),
  );
  const [templateStudio, setTemplateStudio] = useState<ResourceState<TemplateStudio>>(() =>
    emptyResource<TemplateStudio>(),
  );
  const [profiles, setProfiles] = useState<ResourceState<IntegrationProfilesResponse>>(() =>
    emptyResource<IntegrationProfilesResponse>(),
  );
  const [intelligence, setIntelligence] = useState<ResourceState<CaseIntelligence>>(() =>
    emptyResource<CaseIntelligence>(),
  );
  const [splitPreview, setSplitPreview] = useState<ResourceState<SplitPreviewResponse>>(() =>
    emptyResource<SplitPreviewResponse>(),
  );
  const [classification, setClassification] = useState<ResourceState<ClassificationResponse>>(() =>
    emptyResource<ClassificationResponse>(),
  );
  const [validation, setValidation] = useState<ResourceState<ValidationResponse>>(() =>
    emptyResource<ValidationResponse>(),
  );
  const [verification, setVerification] = useState<ResourceState<VerificationResponse>>(() =>
    emptyResource<VerificationResponse>(),
  );
  const [webhook, setWebhook] = useState<ResourceState<WebhookTestResponse>>(() =>
    emptyResource<WebhookTestResponse>(),
  );
  const [reviewLink, setReviewLink] = useState<ResourceState<EmbeddedReviewLinkResponse>>(() =>
    emptyResource<EmbeddedReviewLinkResponse>(),
  );
  const [profileExport, setProfileExport] = useState<ResourceState<ExportProfileResponse>>(() =>
    emptyResource<ExportProfileResponse>(),
  );
  const [reviewWorkbench, setReviewWorkbench] = useState<ResourceState<ReviewWorkbench>>(() =>
    emptyResource<ReviewWorkbench>(),
  );
  const [integrationOps, setIntegrationOps] = useState<ResourceState<IntegrationOperations>>(() =>
    emptyResource<IntegrationOperations>(),
  );
  const [verificationAdapters, setVerificationAdapters] = useState<ResourceState<VerificationAdaptersResponse>>(() =>
    emptyResource<VerificationAdaptersResponse>(),
  );
  const [adapterRun, setAdapterRun] = useState<ResourceState<VerificationAdapterRunResponse>>(() =>
    emptyResource<VerificationAdapterRunResponse>(),
  );
  const [accuracy, setAccuracy] = useState<ResourceState<AccuracyAnalytics>>(() =>
    emptyResource<AccuracyAnalytics>(),
  );
  const activeNav = workspaceNav.find((item) => item.section === section) ?? workspaceNav[0];
  const activeHref = pathname ?? activeNav.href;

  const selectedCase = useMemo(
    () => cases.find((item) => item.id === selectedId) ?? cases[0] ?? null,
    [cases, selectedId],
  );
  const selectedCaseId = selectedCase?.id ?? null;
  const selectedDocument = selectedCase?.documents[0] ?? null;
  const selectedPage = selectedDocument?.pages[0] ?? null;
  const exportProfiles = useMemo(
    () => profiles.data?.export_profiles ?? ["cbs_standard", "los_loan", "aml_case"],
    [profiles.data?.export_profiles],
  );
  const readinessScore = intelligence.data?.readiness_score ?? 0;
  const validationFindings = validation.data?.findings ?? selectedCase?.validation_findings ?? [];
  const packetResults = [...packetDocuments(splitPreview.data), ...packetDocuments(classification.data)].slice(0, 6);
  const reviewField =
    selectedCase?.extracted_fields.find((field) => field.key.includes("citizenship")) ??
    selectedCase?.extracted_fields[0] ??
    null;
  const accuracyRows = Object.entries(accuracy.data?.field_accuracy ?? {}).slice(0, 5);
  const retryEvent = integrationOps.data?.retry_queue[0] ?? null;
  const showCaseIntake = section === "cases";
  const showDocumentIntake = section === "documents";
  const showWorkQueue = ["command", "cases", "documents", "review", "verification", "integrations"].includes(section);
  const showLeftRail = showCaseIntake || showDocumentIntake || showWorkQueue;
  const showRightRail = ["command", "cases", "documents", "review", "verification", "integrations", "admin"].includes(section);
  const productionGridClass =
    section === "command" ? "grid gap-4 xl:grid-cols-3" : section === "templates" ? "grid gap-4 xl:grid-cols-2" : "grid gap-4";
  const workspaceGridClass = showLeftRail
    ? showRightRail
      ? "mx-auto grid max-w-[1720px] gap-5 px-4 py-5 sm:px-6 xl:grid-cols-[300px_minmax(360px,1fr)_360px] 2xl:grid-cols-[340px_minmax(0,1fr)_420px]"
      : "mx-auto grid max-w-[1480px] gap-5 px-4 py-5 sm:px-6 xl:grid-cols-[320px_minmax(0,1fr)] 2xl:grid-cols-[360px_minmax(0,1fr)]"
    : showRightRail
      ? "mx-auto grid max-w-[1480px] gap-5 px-4 py-5 sm:px-6 xl:grid-cols-[minmax(0,1fr)_380px] 2xl:grid-cols-[minmax(0,1fr)_420px]"
      : "mx-auto grid max-w-[1180px] gap-5 px-4 py-5 sm:px-6";

  const summaryCounts = operations.data?.counts ?? {
    total_cases: cases.length,
    documents: cases.reduce((total, item) => total + item.documents.length, 0),
    review_required: cases.filter((item) => item.status === "review_required").length,
    approved: cases.filter((item) => item.status === "approved").length,
    exceptions: cases.filter((item) => item.risk_level === "high").length,
  };

  const mergeCase = useCallback((updated: KycCase) => {
    setCases((current) => {
      const exists = current.some((item) => item.id === updated.id);
      return exists ? current.map((item) => (item.id === updated.id ? updated : item)) : [updated, ...current];
    });
    setSelectedId(updated.id);
  }, []);

  const mergeCaseFromPayload = useCallback(
    (payload: unknown) => {
      if (isKycCase(payload)) {
        mergeCase(payload);
        return;
      }
      if (payload && typeof payload === "object" && "case" in payload && isKycCase(payload.case)) {
        mergeCase(payload.case);
      }
    },
    [mergeCase],
  );

  const loadEnterpriseContext = useCallback(async () => {
    setPlatform((current) => loadingResource(current));
    setOperations((current) => loadingResource(current));
    setOcrPipeline((current) => loadingResource(current));
    setTemplateStudio((current) => loadingResource(current));
    setProfiles((current) => loadingResource(current));
    setAiHealth((current) => loadingResource(current));
    setIntegrationOps((current) => loadingResource(current));
    setVerificationAdapters((current) => loadingResource(current));
    setAccuracy((current) => loadingResource(current));

    await Promise.allSettled([
      apiJson<PlatformStatus>("/api/platform/status", { cache: "no-store" })
        .then((data) => setPlatform(readyResource(data)))
        .catch((error) => setPlatform((current) => failedResource(current, error, "Platform status unavailable"))),
      apiJson<OperationsDashboard>("/api/dashboard/operations", { cache: "no-store" })
        .then((data) => setOperations(readyResource(data)))
        .catch((error) =>
          setOperations((current) => failedResource(current, error, "Operations dashboard unavailable")),
        ),
      apiJson<OcrPipelineProfile>("/api/ocr/pipeline", { cache: "no-store" })
        .then((data) => setOcrPipeline(readyResource(data)))
        .catch((error) => setOcrPipeline((current) => failedResource(current, error, "OCR pipeline unavailable"))),
      apiJson<TemplateStudio>("/api/admin/templates/studio", { cache: "no-store" })
        .then((data) => setTemplateStudio(readyResource(data)))
        .catch((error) => setTemplateStudio((current) => failedResource(current, error, "Template studio unavailable"))),
      apiJson<IntegrationProfilesResponse>("/api/integrations/profiles", { cache: "no-store" })
        .then((data) => setProfiles(readyResource(data)))
        .catch((error) => setProfiles((current) => failedResource(current, error, "Integration profiles unavailable"))),
      apiJson<AiHealth>("/api/ai/health", { cache: "no-store" })
        .then((data) => setAiHealth(readyResource(data)))
        .catch((error) => setAiHealth((current) => failedResource(current, error, "AI health unavailable"))),
      apiJson<IntegrationOperations>("/api/integrations/operations", { cache: "no-store" })
        .then((data) => setIntegrationOps(readyResource(data)))
        .catch((error) =>
          setIntegrationOps((current) => failedResource(current, error, "Integration operations unavailable")),
        ),
      apiJson<VerificationAdaptersResponse>("/api/verification/adapters", { cache: "no-store" })
        .then((data) => setVerificationAdapters(readyResource(data)))
        .catch((error) =>
          setVerificationAdapters((current) => failedResource(current, error, "Verification adapters unavailable")),
        ),
      apiJson<AccuracyAnalytics>("/api/analytics/accuracy", { cache: "no-store" })
        .then((data) => setAccuracy(readyResource(data)))
        .catch((error) => setAccuracy((current) => failedResource(current, error, "Accuracy analytics unavailable"))),
    ]);
  }, []);

  const loadCases = useCallback(async () => {
    setMessage("Syncing");
    try {
      const data = await apiJson<KycCase[]>("/api/cases", { cache: "no-store" });
      setCases(data);
      setSelectedId((current) => current ?? data[0]?.id ?? null);
      setMessage("Connected");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Backend unavailable");
    }
  }, []);

  const refreshAll = useCallback(async () => {
    await Promise.all([loadCases(), loadEnterpriseContext()]);
  }, [loadCases, loadEnterpriseContext]);

  const loadCaseIntelligence = useCallback(async (caseId: string) => {
    setIntelligence((current) => loadingResource(current));
    try {
      const data = await apiJson<CaseIntelligence>(`/api/cases/${caseId}/intelligence`, { cache: "no-store" });
      setIntelligence(readyResource(data));
    } catch (error) {
      setIntelligence((current) => failedResource(current, error, "Case intelligence unavailable"));
    }
  }, []);

  const loadReviewWorkbench = useCallback(async (caseId: string) => {
    setReviewWorkbench((current) => loadingResource(current));
    try {
      const data = await apiJson<ReviewWorkbench>(`/api/review/workbench/${caseId}`, { cache: "no-store" });
      setReviewWorkbench(readyResource(data));
    } catch (error) {
      setReviewWorkbench((current) => failedResource(current, error, "Review workbench unavailable"));
    }
  }, []);

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  useEffect(() => {
    if (!selectedCaseId) {
      setIntelligence(emptyResource<CaseIntelligence>());
      setReviewWorkbench(emptyResource<ReviewWorkbench>());
      return;
    }
    setSplitPreview(emptyResource<SplitPreviewResponse>());
    setClassification(emptyResource<ClassificationResponse>());
    setValidation(emptyResource<ValidationResponse>());
    setVerification(emptyResource<VerificationResponse>());
    setWebhook(emptyResource<WebhookTestResponse>());
    setReviewLink(emptyResource<EmbeddedReviewLinkResponse>());
    setProfileExport(emptyResource<ExportProfileResponse>());
    setAdapterRun(emptyResource<VerificationAdapterRunResponse>());
    void loadCaseIntelligence(selectedCaseId);
    void loadReviewWorkbench(selectedCaseId);
  }, [loadCaseIntelligence, loadReviewWorkbench, selectedCaseId]);

  useEffect(() => {
    if (!exportProfiles.includes(profileKey)) {
      setProfileKey(exportProfiles[0] ?? "cbs_standard");
    }
  }, [exportProfiles, profileKey]);

  async function createCase(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setBusy(true);
    setMessage("Creating case");
    try {
      const created = await apiJson<KycCase>("/api/cases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_type: caseType,
          applicant_name: applicantName,
          customer_ref: customerRef,
          institution_id: "demo-financial-institution",
          branch_code: "KTM-001",
        }),
      });
      mergeCase(created);
      setMessage("Case created");
      void loadEnterpriseContext();
      return created;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Case creation failed");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function uploadDocument(targetCase: KycCase, uploadFile: File, typeOverride?: DocumentType) {
    setBusy(true);
    setMessage("Processing document");
    setExportJson("");
    try {
      const form = new FormData();
      form.append("declared_document_type", typeOverride ?? documentType);
      form.append("file", uploadFile);
      const updated = await apiJson<KycCase>(`/api/cases/${targetCase.id}/documents`, {
        method: "POST",
        body: form,
      });
      mergeCase(updated);
      setMessage("Document processed");
      void loadCaseIntelligence(updated.id);
      void loadEnterpriseContext();
      return updated;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Document processing failed");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || !selectedCase) {
      return;
    }
    await uploadDocument(selectedCase, file);
  }

  async function runSamplePacket() {
    let target: KycCase | null = selectedCase;
    if (!target) {
      target = await createCase();
    }
    if (!target) {
      return;
    }
    const samples: { type: DocumentType; name: string; text: string }[] = [
      {
        type: "citizenship",
        name: "np-citizenship.txt",
        text: "Government of Nepal\nName: Sita Sharma\nCitizenship No: 27-01-78-12345\nDistrict: Kathmandu\nPhoto attached\nSignature present",
      },
      {
        type: "account_opening",
        name: "account-opening-form.txt",
        text: "Account Opening Form\nCustomer Name: Sita Sharma\nMobile: 9841000000\nAddress: Kathmandu\nAccount Type: Savings\nCustomer Declaration Signed",
      },
      {
        type: "pan",
        name: "pan-certificate.txt",
        text: "Permanent Account Number\nName: Sita Sharma\nPAN: 123456789",
      },
    ];
    let currentCase = target;
    for (const sample of samples) {
      const fileBlob = new File([sample.text], sample.name, { type: "text/plain" });
      const updated = await uploadDocument(currentCase, fileBlob, sample.type);
      if (updated) {
        currentCase = updated;
      }
    }
  }

  async function runCaseAction<T>(
    action: string,
    label: string,
    path: string,
    setter: (updater: (current: ResourceState<T>) => ResourceState<T>) => void,
  ) {
    if (!selectedCase) {
      return null;
    }
    setBusy(true);
    setActiveAction(action);
    setMessage(label);
    setter((current) => loadingResource(current));
    try {
      const data = await apiJson<T>(path, { method: "POST", headers: { "Content-Type": "application/json" } });
      setter(() => readyResource(data));
      mergeCaseFromPayload(data);
      setMessage(`${label} complete`);
      void loadEnterpriseContext();
      return data;
    } catch (error) {
      setter((current) => failedResource(current, error, `${label} failed`));
      setMessage(error instanceof Error ? error.message : `${label} failed`);
      return null;
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function approveCase() {
    if (!selectedCase) {
      return;
    }
    setBusy(true);
    setActiveAction("approve");
    setMessage("Approving");
    try {
      const updated = await apiJson<KycCase>(`/api/cases/${selectedCase.id}/review`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reviewer: "checker.one",
          decision: "approve",
          field_updates: {},
          note: "Maker-checker review complete.",
        }),
      });
      mergeCase(updated);
      setMessage("Approved");
      void loadEnterpriseContext();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Approval failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function exportProfile() {
    if (!selectedCase) {
      return;
    }
    setBusy(true);
    setActiveAction("export-profile");
    setMessage("Exporting profile");
    setProfileExport((current) => loadingResource(current));
    try {
      const data = await apiJson<ExportProfileResponse>(
        `/api/cases/${selectedCase.id}/export-profile/${encodeURIComponent(profileKey)}`,
        { cache: "no-store" },
      );
      setProfileExport(readyResource(data));
      setExportJson(JSON.stringify(data, null, 2));
      setMessage("Export profile ready");
      void loadEnterpriseContext();
    } catch (error) {
      setProfileExport((current) => failedResource(current, error, "Export profile failed"));
      setMessage(error instanceof Error ? error.message : "Export profile failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function testWebhook() {
    if (!selectedCase) {
      return;
    }
    setBusy(true);
    setActiveAction("webhook");
    setMessage("Testing webhook");
    setWebhook((current) => loadingResource(current));
    try {
      const data = await apiJson<WebhookTestResponse>("/api/integrations/webhook/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ case_id: selectedCase.id, event: "case.review_required" }),
      });
      setWebhook(readyResource(data));
      setMessage("Webhook signed");
    } catch (error) {
      setWebhook((current) => failedResource(current, error, "Webhook test failed"));
      setMessage(error instanceof Error ? error.message : "Webhook test failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function createReviewLink() {
    if (!selectedCase) {
      return;
    }
    setBusy(true);
    setActiveAction("review-link");
    setMessage("Creating review link");
    setReviewLink((current) => loadingResource(current));
    try {
      const data = await apiJson<EmbeddedReviewLinkResponse>(`/api/cases/${selectedCase.id}/embedded-review-link`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      setReviewLink(readyResource(data));
      setMessage("Review link ready");
    } catch (error) {
      setReviewLink((current) => failedResource(current, error, "Review link failed"));
      setMessage(error instanceof Error ? error.message : "Review link failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function assignReviewer() {
    if (!selectedCase) {
      return;
    }
    setBusy(true);
    setActiveAction("assign-reviewer");
    setMessage("Assigning reviewer");
    setReviewWorkbench((current) => loadingResource(current));
    try {
      const data = await apiJson<AssignmentResponse>(`/api/cases/${selectedCase.id}/assign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reviewer: "checker.two", queue: "high_value_kyc", priority: "high" }),
      });
      mergeCaseFromPayload(data);
      setMessage("Reviewer assigned");
      void loadReviewWorkbench(selectedCase.id);
      void loadEnterpriseContext();
    } catch (error) {
      setReviewWorkbench((current) => failedResource(current, error, "Reviewer assignment failed"));
      setMessage(error instanceof Error ? error.message : "Reviewer assignment failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function addReviewComment() {
    if (!selectedCase) {
      return;
    }
    setBusy(true);
    setActiveAction("review-comment");
    setMessage("Adding review note");
    try {
      await apiJson<CommentResponse>(`/api/cases/${selectedCase.id}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          author: "checker.two",
          message: "Evidence crop and registry result need checker confirmation.",
          field_key: reviewField?.key ?? "case",
        }),
      });
      setMessage("Review note added");
      void loadReviewWorkbench(selectedCase.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Review note failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function requestRework() {
    if (!selectedCase) {
      return;
    }
    setBusy(true);
    setActiveAction("request-rework");
    setMessage("Requesting maker rework");
    try {
      const updated = await apiJson<KycCase>(`/api/cases/${selectedCase.id}/rework`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          requester: "checker.two",
          reason: "Source evidence must be refreshed before final approval.",
          fields: reviewField ? [reviewField.key] : [],
        }),
      });
      mergeCase(updated);
      setMessage("Rework requested");
      void loadReviewWorkbench(updated.id);
      void loadEnterpriseContext();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Rework request failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function recordCorrection() {
    if (!selectedCase || !reviewField) {
      return;
    }
    setBusy(true);
    setActiveAction("record-correction");
    setMessage("Recording correction");
    setAccuracy((current) => loadingResource(current));
    try {
      const correctedValue = reviewField.value ? `${reviewField.value} / verified` : "verified-by-reviewer";
      const data = await apiJson<CorrectionResponse>("/api/analytics/corrections", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: selectedCase.id,
          field_key: reviewField.key,
          old_value: reviewField.value,
          new_value: correctedValue,
          corrected_by: "checker.two",
          document_type: selectedDocument?.document_type ?? "unknown",
        }),
      });
      mergeCaseFromPayload(data);
      setMessage("Correction recorded");
      void loadReviewWorkbench(selectedCase.id);
      void loadEnterpriseContext();
    } catch (error) {
      setAccuracy((current) => failedResource(current, error, "Correction failed"));
      setMessage(error instanceof Error ? error.message : "Correction failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function configureTemplate() {
    setBusy(true);
    setActiveAction("configure-template");
    setMessage("Configuring National ID template");
    setTemplateStudio((current) => loadingResource(current));
    try {
      const data = await apiJson<{ studio: TemplateStudio }>("/api/admin/templates/studio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_type: "national_id",
          name: "Nepal National ID Card",
          fields: [
            { key: "national_id_number", label: "National ID Number", required: true, bbox: [100, 120, 520, 170] },
            { key: "full_name", label: "Full Name", required: true, bbox: [100, 180, 650, 230] },
            { key: "date_of_birth", label: "Date of Birth", required: true, bbox: [100, 238, 420, 286] },
          ],
          validation_rules: [
            { field_key: "national_id_number", rule: "required", severity: "error" },
            { field_key: "date_of_birth", rule: "date", severity: "warning" },
          ],
        }),
      });
      setTemplateStudio(readyResource(data.studio));
      setMessage("Template configured");
    } catch (error) {
      setTemplateStudio((current) => failedResource(current, error, "Template configuration failed"));
      setMessage(error instanceof Error ? error.message : "Template configuration failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function configurePanAdapter() {
    setBusy(true);
    setActiveAction("configure-pan");
    setMessage("Configuring PAN adapter");
    setVerificationAdapters((current) => loadingResource(current));
    try {
      await apiJson<{ adapter: VerificationAdapter }>("/api/verification/adapters/pan_registry/configure", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "sandbox", endpoint: "https://ird.example.local/pan", enabled: true }),
      });
      const adapters = await apiJson<VerificationAdaptersResponse>("/api/verification/adapters", { cache: "no-store" });
      setVerificationAdapters(readyResource(adapters));
      setMessage("PAN adapter configured");
    } catch (error) {
      setVerificationAdapters((current) => failedResource(current, error, "PAN adapter configuration failed"));
      setMessage(error instanceof Error ? error.message : "PAN adapter configuration failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function runPanAdapter() {
    if (!selectedCase) {
      return;
    }
    setBusy(true);
    setActiveAction("run-pan");
    setMessage("Running PAN adapter");
    setAdapterRun((current) => loadingResource(current));
    try {
      const data = await apiJson<VerificationAdapterRunResponse>(
        `/api/cases/${selectedCase.id}/verification/pan_registry/run`,
        { method: "POST", headers: { "Content-Type": "application/json" } },
      );
      setAdapterRun(readyResource(data));
      mergeCaseFromPayload(data);
      setMessage("PAN adapter run complete");
      void loadReviewWorkbench(selectedCase.id);
    } catch (error) {
      setAdapterRun((current) => failedResource(current, error, "PAN adapter run failed"));
      setMessage(error instanceof Error ? error.message : "PAN adapter run failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function configureCoreWebhook() {
    setBusy(true);
    setActiveAction("configure-webhook");
    setMessage("Configuring CBS webhook");
    setIntegrationOps((current) => loadingResource(current));
    try {
      await apiJson<{ webhook: IntegrationOperations["webhooks"][number] }>("/api/integrations/webhooks/configure", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          key: "cbs_core",
          url: "https://cbs.example.local/hooks/kyc",
          events: ["case.approved", "case.rejected", "review.required"],
        }),
      });
      setMessage("CBS webhook configured");
      void loadEnterpriseContext();
    } catch (error) {
      setIntegrationOps((current) => failedResource(current, error, "Webhook configuration failed"));
      setMessage(error instanceof Error ? error.message : "Webhook configuration failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function queueSftpBatch() {
    if (!selectedCase) {
      return;
    }
    setBusy(true);
    setActiveAction("queue-sftp");
    setMessage("Queueing SFTP batch");
    setIntegrationOps((current) => loadingResource(current));
    try {
      await apiJson<IntegrationOperations["retry_queue"][number]>("/api/integrations/sftp/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile_key: profileKey,
          target: "sftp://core-bank.example/outbound",
          case_ids: [selectedCase.id],
        }),
      });
      setMessage("SFTP batch queued");
      void loadEnterpriseContext();
    } catch (error) {
      setIntegrationOps((current) => failedResource(current, error, "SFTP batch failed"));
      setMessage(error instanceof Error ? error.message : "SFTP batch failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function retryIntegration() {
    if (!retryEvent) {
      return;
    }
    setBusy(true);
    setActiveAction("retry-integration");
    setMessage("Scheduling retry");
    setIntegrationOps((current) => loadingResource(current));
    try {
      await apiJson<{ event: IntegrationOperations["retry_queue"][number] }>(
        `/api/integrations/retry/${retryEvent.event_id}`,
        { method: "POST", headers: { "Content-Type": "application/json" } },
      );
      setMessage("Retry scheduled");
      void loadEnterpriseContext();
    } catch (error) {
      setIntegrationOps((current) => failedResource(current, error, "Retry failed"));
      setMessage(error instanceof Error ? error.message : "Retry failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950">
      <header className="sticky top-0 z-30 border-b border-border-soft/80 bg-white/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1800px] flex-col gap-4 px-4 py-4 sm:px-6 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-indigo-600">LipiOCR Enterprise</p>
            <h1 className="mt-1 text-3xl font-extrabold text-slate-950">{activeNav.label}</h1>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">{activeNav.description}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Pill icon={<Activity size={16} />} label={message} />
            <Pill icon={<BrainCircuit size={16} />} label={aiHealth.data?.model ?? "gemma-4-26b-4bit"} />
            <Pill icon={<Route size={16} />} label={platform.data?.deployment_target ?? "on-prem/private"} />
            <button
              className="inline-flex h-10 items-center gap-2 rounded-full border border-slate-200 bg-white px-4 font-semibold text-slate-700 shadow-[var(--shadow-soft)] hover:-translate-y-0.5 hover:border-indigo-200 hover:text-indigo-700 hover:shadow-[var(--shadow-lift)]"
              onClick={refreshAll}
              type="button"
            >
              <RefreshCcw size={16} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      <section className="border-b border-border-soft/80 bg-slate-50/70">
        <div className="mx-auto max-w-[1800px] px-4 pt-4 sm:px-6">
          <ModuleSwitcher activeHref={activeHref} activeSection={section} />
        </div>
        <div className="mx-auto grid max-w-[1800px] gap-3 px-4 py-4 sm:px-6 lg:grid-cols-5">
          <Kpi icon={<Boxes size={18} />} label="Cases" value={summaryCounts.total_cases} />
          <Kpi icon={<ClipboardCheck size={18} />} label="Review" value={summaryCounts.review_required} />
          <Kpi icon={<ShieldAlert size={18} />} label="Exceptions" value={summaryCounts.exceptions} />
          <Kpi icon={<BadgeCheck size={18} />} label="Approved" value={summaryCounts.approved} />
          <Kpi icon={<FileText size={18} />} label="Documents" value={summaryCounts.documents} />
        </div>
      </section>

      <div className={workspaceGridClass}>
        {showLeftRail ? (
        <aside className="space-y-4">
          {section === "cases" ? (
          <Panel title="Intake" icon={<Upload size={16} />}>
            <form className="space-y-3" onSubmit={createCase}>
              <FieldLabel label="Case Type">
                <select
                  className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
                  value={caseType}
                  onChange={(event) => setCaseType(event.target.value as CaseType)}
                >
                  {caseTypes.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </FieldLabel>
              <FieldLabel label="Applicant">
                <input
                  className="h-10 w-full rounded-xl border border-slate-200 px-3 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
                  value={applicantName}
                  onChange={(event) => setApplicantName(event.target.value)}
                />
              </FieldLabel>
              <FieldLabel label="CBS / LOS Ref">
                <input
                  className="h-10 w-full rounded-xl border border-slate-200 px-3 font-mono text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
                  value={customerRef}
                  onChange={(event) => setCustomerRef(event.target.value)}
                />
              </FieldLabel>
              <button
                className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-full bg-gradient-to-r from-indigo-600 to-violet-600 px-3 text-sm font-bold text-white shadow-[var(--shadow-button)] hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)] disabled:opacity-60"
                disabled={busy}
                type="submit"
              >
                {busy && activeAction === null ? <Loader2 className="animate-spin" size={16} /> : <Plus size={16} />}
                Create Case
              </button>
            </form>
          </Panel>
          ) : null}

          {section === "documents" ? (
          <Panel title="Document Intake" icon={<FileCog size={16} />}>
            <form className="space-y-3" onSubmit={handleUpload}>
              <FieldLabel label="Document Type">
                <select
                  className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
                  value={documentType}
                  onChange={(event) => setDocumentType(event.target.value as DocumentType)}
                >
                  {documentTypes.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </FieldLabel>
              <label className="flex min-h-28 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-indigo-200 bg-indigo-50/60 px-3 text-center hover:-translate-y-0.5 hover:border-indigo-300 hover:bg-indigo-50">
                <Upload className="mb-2 text-indigo-600" size={22} />
                <span className="max-w-full truncate text-sm font-medium">{file?.name ?? "Choose document"}</span>
                <input className="sr-only" type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
              </label>
              <div className="grid grid-cols-2 gap-2">
                <ActionButton disabled={busy || !file || !selectedCase} icon={<Upload size={14} />} type="submit">
                  Upload
                </ActionButton>
                <ActionButton busy={busy && message.includes("Processing")} icon={<Layers3 size={14} />} onClick={runSamplePacket}>
                  Full Packet
                </ActionButton>
              </div>
            </form>
          </Panel>
          ) : null}

          <Panel title="Work Queue" icon={<Workflow size={16} />}>
            <div className="space-y-3">
              <div className="grid gap-2">
                {(operations.data?.lanes ?? []).map((lane) => (
                  <button
                    className="grid grid-cols-[1fr_auto] gap-2 rounded-xl border border-slate-200 bg-white p-3 text-left shadow-sm hover:-translate-y-0.5 hover:border-indigo-200 hover:shadow-[var(--shadow-soft)]"
                    key={lane.key}
                    type="button"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-semibold">{lane.label}</span>
                      <span className="block truncate text-xs text-slate-500">{lane.description}</span>
                    </span>
                    <span className="font-mono text-lg font-semibold">{lane.count}</span>
                  </button>
                ))}
              </div>
              <div className="max-h-[420px] overflow-auto">
                {cases.length ? (
                  cases.map((item) => (
                    <button
                      className={`mb-2 block w-full rounded-xl border p-3 text-left shadow-sm hover:-translate-y-0.5 hover:border-indigo-200 hover:shadow-[var(--shadow-soft)] ${
                        selectedCase?.id === item.id ? "border-indigo-300 bg-indigo-50 text-indigo-950" : "border-slate-200 bg-white"
                      }`}
                      key={item.id}
                      onClick={() => {
                        setSelectedId(item.id);
                        setExportJson("");
                      }}
                      type="button"
                    >
                      <span className="flex items-start justify-between gap-2">
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-semibold">{item.applicant_name}</span>
                          <span className="block truncate font-mono text-xs text-slate-500">
                            {item.integration_ref ?? compactId(item.id)}
                          </span>
                        </span>
                        <StatusBadge status={item.status} />
                      </span>
                      <span className="mt-2 flex items-center justify-between text-xs text-slate-500">
                        <span>{labelize(item.case_type)}</span>
                        <span>{item.documents.length} docs</span>
                      </span>
                    </button>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">No active cases</p>
                )}
              </div>
            </div>
          </Panel>
        </aside>
        ) : null}

        <section className="space-y-4">
          {["command", "admin"].includes(section) ? (
          <Panel title="Platform Readiness" icon={<Gauge size={16} />}>
            <ResourceError resource={platform} />
            <div className="grid gap-2 lg:grid-cols-3">
              {(platform.data?.components ?? []).map((component) => (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3" key={component.key}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold">{component.label}</p>
                      <p className="mt-1 truncate text-xs text-slate-500">{component.detail}</p>
                    </div>
                    <StatusBadge status={component.status} />
                  </div>
                  <p className="mt-3 line-clamp-2 text-xs text-slate-600">{component.next_step}</p>
                </div>
              ))}
            </div>
          </Panel>
          ) : null}

          {["cases", "documents", "review", "verification"].includes(section) ? (
          <Panel title={selectedCase?.applicant_name ?? "Case Workbench"} icon={<Eye size={16} />}>
            {selectedCase ? (
              <div className="grid gap-4 2xl:grid-cols-[minmax(360px,0.95fr)_minmax(420px,1.05fr)]">
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                    <Info label="Case" value={compactId(selectedCase.id)} />
                    <Info label="Type" value={labelize(selectedCase.case_type)} />
                    <Info label="Branch" value={selectedCase.branch_code ?? "KTM-001"} />
                    <Info label="Readiness" value={pct(readinessScore)} />
                  </div>
                  <div className="relative aspect-[0.72] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-inner">
                    <div className="absolute inset-x-5 top-5 flex items-start justify-between border-b border-slate-200 pb-3">
                      <div className="min-w-0">
                        <p className="text-xs font-semibold uppercase text-slate-500">
                          {selectedDocument ? labelize(selectedDocument.document_type) : "Document Packet"}
                        </p>
                        <p className="mt-1 truncate text-lg font-semibold">
                          {selectedDocument?.filename ?? "No document uploaded"}
                        </p>
                      </div>
                      <FileText className="shrink-0 text-indigo-600" size={26} />
                    </div>
                    {selectedPage ? (
                      selectedPage.blocks.map((block, index) => (
                        <div
                          className="absolute overflow-hidden rounded-sm border border-indigo-500 bg-indigo-100/70 px-1.5 py-1 text-[10px] font-semibold leading-tight text-indigo-950"
                          key={`${block.text}-${index}`}
                          style={blockStyle(block, selectedPage)}
                          title={block.text}
                        >
                          <span className="block truncate">{block.text}</span>
                          <span className="block font-mono">{pct(block.confidence)}</span>
                        </div>
                      ))
                    ) : (
                      <div className="absolute inset-x-6 top-28 text-sm text-slate-500">No OCR evidence yet.</div>
                    )}
                  </div>
                </div>

                <div className="min-w-0 space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <ActionButton
                      busy={activeAction === "split"}
                      disabled={busy}
                      icon={<SplitSquareHorizontal size={14} />}
                      onClick={() =>
                        runCaseAction<SplitPreviewResponse>(
                          "split",
                          "Building split preview",
                          `/api/cases/${selectedCase.id}/split-preview`,
                          setSplitPreview,
                        )
                      }
                    >
                      Split
                    </ActionButton>
                    <ActionButton
                      busy={activeAction === "classify"}
                      disabled={busy}
                      icon={<FileSearch size={14} />}
                      onClick={() =>
                        runCaseAction<ClassificationResponse>(
                          "classify",
                          "Classifying packet",
                          `/api/cases/${selectedCase.id}/classify`,
                          setClassification,
                        )
                      }
                    >
                      Classify
                    </ActionButton>
                    <ActionButton
                      busy={activeAction === "validate"}
                      disabled={busy}
                      icon={<ClipboardCheck size={14} />}
                      onClick={() =>
                        runCaseAction<ValidationResponse>(
                          "validate",
                          "Running validation",
                          `/api/cases/${selectedCase.id}/validate`,
                          setValidation,
                        )
                      }
                    >
                      Validate
                    </ActionButton>
                    <ActionButton
                      busy={activeAction === "verify"}
                      disabled={busy}
                      icon={<Play size={14} />}
                      onClick={() =>
                        runCaseAction<VerificationResponse>(
                          "verify",
                          "Running verification",
                          `/api/cases/${selectedCase.id}/verification/run`,
                          setVerification,
                        )
                      }
                      tone="primary"
                    >
                      Verify
                    </ActionButton>
                    <ActionButton
                      busy={activeAction === "approve"}
                      disabled={busy}
                      icon={<ShieldCheck size={14} />}
                      onClick={approveCase}
                      tone="primary"
                    >
                      Approve
                    </ActionButton>
                  </div>

                  <div className="rounded-xl border border-slate-200">
                    <div className="grid grid-cols-[1fr_96px_120px] border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase text-slate-500">
                      <span>Field</span>
                      <span>Confidence</span>
                      <span>Evidence</span>
                    </div>
                    <div className="max-h-[380px] overflow-auto">
                      {selectedCase.extracted_fields.length ? (
                        selectedCase.extracted_fields.map((field) => (
                          <div
                            className="grid gap-2 border-b border-slate-100 p-3 last:border-b-0 sm:grid-cols-[1fr_96px_120px]"
                            key={`${field.key}-${field.document_id ?? ""}`}
                          >
                            <div className="min-w-0">
                              <p className="text-xs font-semibold text-slate-500">{field.label}</p>
                              <p className="mt-1 truncate text-sm font-medium">{field.value || "Unclear"}</p>
                              <p className="mt-1 truncate text-xs text-slate-500">{field.validation_message}</p>
                            </div>
                            <div className="flex items-center">
                              <span className="rounded-xl bg-slate-100 px-2 py-1 font-mono text-xs">
                                {pct(field.confidence)}
                              </span>
                            </div>
                            <div className="min-w-0 text-xs">
                              <p className="font-mono text-slate-600">p{field.evidence.source_page}</p>
                              <p className="truncate text-slate-500">{field.evidence.evidence_text}</p>
                              <p className="mt-1 truncate text-indigo-600">{field.extracted_by}</p>
                            </div>
                          </div>
                        ))
                      ) : (
                        <p className="p-4 text-sm text-slate-500">No extracted fields</p>
                      )}
                    </div>
                  </div>

                  {packetResults.length ? (
                    <div className="grid gap-2 md:grid-cols-2">
                      {packetResults.map((document, index) => (
                        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs" key={`${document.document_id}-${index}`}>
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <p className="truncate font-semibold">
                                {labelize(document.predicted_type ?? document.document_type)}
                              </p>
                              <p className="mt-1 truncate text-slate-500">{document.filename ?? document.reason}</p>
                            </div>
                            <span className="font-mono">{pct(document.confidence)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            ) : (
              <div className="p-8 text-sm text-slate-500">Create or select a case.</div>
            )}
          </Panel>
          ) : null}

          {section === "integrations" ? (
          <Panel title="Integration Directory" icon={<Plug size={16} />}>
            <ResourceError resource={profiles} />
            <div className="grid gap-2 lg:grid-cols-2">
              {(profiles.data?.profiles ?? []).map((profile) => (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs" key={profile.key}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate font-semibold">{profile.name}</p>
                      <p className="mt-1 truncate text-slate-500">
                        {labelize(profile.category)} · {labelize(profile.mode)}
                      </p>
                    </div>
                    <StatusBadge status={profile.status} />
                  </div>
                  <p className="mt-3 line-clamp-2 text-slate-600">{profile.description}</p>
                </div>
              ))}
            </div>
          </Panel>
          ) : null}

          {["command", "templates", "analytics"].includes(section) ? (
          <Panel title="Production Pipeline" icon={<SearchCheck size={16} />}>
            <div className={productionGridClass}>
              {section !== "analytics" ? (
              <div className="space-y-2">
                <SectionLabel icon={<FileSearch size={15} />} label={`OCR: ${ocrPipeline.data?.active_provider ?? "loading"}`} />
                {(ocrPipeline.data?.providers ?? []).map((provider) => (
                  <div className="grid grid-cols-[1fr_auto] gap-3 rounded-xl border border-slate-200 p-3 text-xs" key={provider.key}>
                    <div className="min-w-0">
                      <p className="truncate font-semibold">{provider.label}</p>
                      <p className="mt-1 truncate text-slate-500">{provider.best_for}</p>
                    </div>
                    <StatusBadge status={provider.status} />
                  </div>
                ))}
              </div>
              ) : null}
              {section !== "analytics" ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <SectionLabel icon={<FileCog size={15} />} label="Template Studio" />
                  <ActionButton
                    busy={activeAction === "configure-template"}
                    disabled={busy}
                    icon={<FileCog size={14} />}
                    onClick={configureTemplate}
                  >
                    NID
                  </ActionButton>
                </div>
                <ResourceError resource={templateStudio} />
                {(templateStudio.data?.templates ?? []).slice(0, 6).map((template) => (
                  <div className="grid grid-cols-[1fr_auto] gap-3 rounded-xl border border-slate-200 p-3 text-xs" key={template.document_type}>
                    <div className="min-w-0">
                      <p className="truncate font-semibold">{template.name}</p>
                      <p className="mt-1 truncate text-slate-500">
                        {template.field_count} fields · {labelize(template.mode)}
                      </p>
                    </div>
                    <StatusBadge status={template.status} />
                  </div>
                ))}
              </div>
              ) : null}
              {section !== "templates" ? (
              <div className="space-y-2">
                <SectionLabel icon={<Gauge size={15} />} label={`Accuracy: ${accuracy.data?.correction_count ?? 0} corrections`} />
                <ResourceError resource={accuracy} />
                {accuracyRows.length ? (
                  accuracyRows.map(([fieldKey, row]) => (
                    <div className="grid grid-cols-[1fr_auto] gap-3 rounded-xl border border-slate-200 p-3 text-xs" key={fieldKey}>
                      <div className="min-w-0">
                        <p className="truncate font-semibold">{labelize(fieldKey)}</p>
                        <p className="mt-1 truncate text-slate-500">
                          {row.observed} observed · {row.corrections} corrected
                        </p>
                      </div>
                      <span className="font-mono font-semibold">{pct(row.estimated_accuracy)}</span>
                    </div>
                  ))
                ) : (
                  <p className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500">
                    Reviewer corrections will populate accuracy drift.
                  </p>
                )}
              </div>
              ) : null}
            </div>
          </Panel>
          ) : null}
        </section>

        {showRightRail ? (
        <aside className="space-y-4">
          {["command", "cases", "documents"].includes(section) ? (
          <Panel title="Decision Rail" icon={<Fingerprint size={16} />}>
            <ResourceError resource={intelligence} />
            <div className="grid grid-cols-3 gap-2">
              <Info label="Ready" value={pct(readinessScore)} />
              <Info label="Risk" value={pct(intelligence.data?.risk_score)} />
              <Info label="Gaps" value={`${intelligence.data?.gaps.length ?? 0}`} />
            </div>
            <div className="mt-3 space-y-2">
              {(intelligence.data?.checklist ?? []).map((item) => (
                <div className="grid grid-cols-[1fr_auto] gap-3 rounded-xl border border-slate-200 p-3 text-xs" key={item.key}>
                  <div className="min-w-0">
                    <p className="truncate font-semibold">{item.label}</p>
                    <p className="mt-1 truncate text-slate-500">{item.message}</p>
                  </div>
                  <StatusBadge status={item.status} />
                </div>
              ))}
            </div>
          </Panel>
          ) : null}

          {section === "review" ? (
          <Panel title="Reviewer Workbench" icon={<ClipboardCheck size={16} />}>
            <ResourceError resource={reviewWorkbench} />
            <div className="grid grid-cols-3 gap-2">
              <Info label="Owner" value={reviewWorkbench.data?.assignment.reviewer ?? selectedCase?.review.reviewer ?? "unassigned"} />
              <Info label="Queue" value={labelize(reviewWorkbench.data?.assignment.queue ?? "standard_kyc")} />
              <Info label="Priority" value={labelize(reviewWorkbench.data?.assignment.priority ?? selectedCase?.risk_level ?? "normal")} />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <ActionButton
                busy={activeAction === "assign-reviewer"}
                disabled={busy || !selectedCase}
                icon={<ClipboardCheck size={14} />}
                onClick={assignReviewer}
              >
                Assign
              </ActionButton>
              <ActionButton
                busy={activeAction === "review-comment"}
                disabled={busy || !selectedCase}
                icon={<FileText size={14} />}
                onClick={addReviewComment}
              >
                Comment
              </ActionButton>
              <ActionButton
                busy={activeAction === "request-rework"}
                disabled={busy || !selectedCase}
                icon={<RefreshCcw size={14} />}
                onClick={requestRework}
              >
                Rework
              </ActionButton>
              <ActionButton
                busy={activeAction === "record-correction"}
                disabled={busy || !selectedCase || !reviewField}
                icon={<Gauge size={14} />}
                onClick={recordCorrection}
              >
                Correction
              </ActionButton>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2">
              <Info label="Notes" value={`${reviewWorkbench.data?.comments.length ?? 0}`} />
              <Info label="Rework" value={`${reviewWorkbench.data?.rework_requests.length ?? 0}`} />
              <Info label="Crops" value={`${reviewWorkbench.data?.evidence_crops.length ?? 0}`} />
            </div>
            <div className="mt-3 max-h-48 space-y-2 overflow-auto pr-1">
              {(reviewWorkbench.data?.comments ?? []).slice(-3).map((comment) => (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs" key={comment.comment_id}>
                  <div className="flex items-start justify-between gap-2">
                    <p className="truncate font-semibold">{comment.author}</p>
                    <span className="font-mono text-slate-500">{formatDate(comment.created_at)}</span>
                  </div>
                  <p className="mt-1 line-clamp-2 text-slate-600">{comment.message}</p>
                </div>
              ))}
              {(reviewWorkbench.data?.rework_requests ?? []).slice(-2).map((request) => (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs" key={request.request_id}>
                  <div className="flex items-start justify-between gap-2">
                    <p className="truncate font-semibold text-amber-900">{request.reason}</p>
                    <StatusBadge status={request.status} />
                  </div>
                  <p className="mt-1 truncate text-amber-800">{request.fields.join(", ") || "case-level"}</p>
                </div>
              ))}
            </div>
          </Panel>
          ) : null}

          {section === "verification" ? (
          <Panel title="Verification" icon={<LockKeyhole size={16} />}>
            <div className="grid grid-cols-3 gap-2">
              <Info label="Decision" value={verification.data?.decision ?? "pending"} />
              <Info label="Score" value={pct(verification.data?.score)} />
              <Info label="Run" value={compactId(verification.data?.run_id)} />
            </div>
            <div className="mt-3 max-h-72 space-y-2 overflow-auto pr-1">
              {validationFindings.map((finding, index) => (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs" key={`${finding.code}-${index}`}>
                  <div className="flex items-start justify-between gap-2">
                    <p className="min-w-0 truncate font-semibold text-amber-900">{finding.code}</p>
                    <StatusBadge status={finding.severity} />
                  </div>
                  <p className="mt-1 line-clamp-2 text-amber-800">{finding.message}</p>
                </div>
              ))}
              {(verification.data?.checks ?? []).map((check) => (
                <div className="grid grid-cols-[1fr_auto] gap-3 rounded-xl border border-slate-200 p-3 text-xs" key={check.key}>
                  <div className="min-w-0">
                    <p className="truncate font-semibold">{check.label}</p>
                    <p className="mt-1 line-clamp-2 text-slate-500">{check.message}</p>
                  </div>
                  <StatusBadge status={check.status} />
                </div>
              ))}
              {!validationFindings.length && !verification.data?.checks.length ? (
                <p className="text-sm text-slate-500">No validation or verification output</p>
              ) : null}
            </div>
          </Panel>
          ) : null}

          {section === "verification" ? (
          <Panel title="Adapter Registry" icon={<Route size={16} />}>
            <ResourceError resource={verificationAdapters} />
            <ResourceError resource={adapterRun} />
            <div className="grid grid-cols-2 gap-2">
              <ActionButton
                busy={activeAction === "configure-pan"}
                disabled={busy}
                icon={<FileCog size={14} />}
                onClick={configurePanAdapter}
              >
                Configure PAN
              </ActionButton>
              <ActionButton
                busy={activeAction === "run-pan"}
                disabled={busy || !selectedCase}
                icon={<Play size={14} />}
                onClick={runPanAdapter}
                tone="primary"
              >
                Run PAN
              </ActionButton>
            </div>
            {adapterRun.data ? (
              <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs">
                <div className="flex items-start justify-between gap-2">
                  <p className="truncate font-semibold">{adapterRun.data.check.label}</p>
                  <StatusBadge status={adapterRun.data.check.status} />
                </div>
                <p className="mt-1 line-clamp-2 text-slate-600">{adapterRun.data.check.message}</p>
              </div>
            ) : null}
            <div className="mt-3 max-h-56 space-y-2 overflow-auto pr-1">
              {(verificationAdapters.data?.adapters ?? []).map((adapter) => (
                <div className="grid grid-cols-[1fr_auto] gap-3 rounded-xl border border-slate-200 p-3 text-xs" key={adapter.key}>
                  <div className="min-w-0">
                    <p className="truncate font-semibold">{adapter.label}</p>
                    <p className="mt-1 truncate text-slate-500">{labelize(adapter.mode)}</p>
                  </div>
                  <StatusBadge status={adapter.status} />
                </div>
              ))}
            </div>
          </Panel>
          ) : null}

          {section === "integrations" ? (
          <Panel title="Integration Handoff" icon={<Plug size={16} />}>
            <div className="space-y-3">
              <FieldLabel label="Export Profile">
                <select
                  className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
                  value={profileKey}
                  onChange={(event) => setProfileKey(event.target.value)}
                >
                  {exportProfiles.map((key) => (
                    <option key={key} value={key}>
                      {labelize(key)}
                    </option>
                  ))}
                </select>
              </FieldLabel>
              <div className="grid grid-cols-2 gap-2">
                <ActionButton
                  busy={activeAction === "webhook"}
                  disabled={busy || !selectedCase}
                  icon={<Network size={14} />}
                  onClick={testWebhook}
                >
                  Webhook
                </ActionButton>
                <ActionButton
                  busy={activeAction === "review-link"}
                  disabled={busy || !selectedCase}
                  icon={<Link2 size={14} />}
                  onClick={createReviewLink}
                >
                  Link
                </ActionButton>
                <ActionButton
                  className="col-span-2"
                  busy={activeAction === "export-profile"}
                  disabled={busy || !selectedCase}
                  icon={<Download size={14} />}
                  onClick={exportProfile}
                  tone="primary"
                >
                  Export
                </ActionButton>
              </div>
              <ResourceError resource={webhook} />
              <ResourceError resource={reviewLink} />
              <ResourceError resource={profileExport} />
              {webhook.data ? (
                <InfoBox label="Webhook" value={`${webhook.data.status} · ${compactId(webhook.data.event_id)}`} />
              ) : null}
              {reviewLink.data ? <InfoBox label="Review Link" value={reviewLink.data.url} /> : null}
            </div>
          </Panel>
          ) : null}

          {section === "integrations" ? (
          <Panel title="Integration Operations" icon={<Network size={16} />}>
            <ResourceError resource={integrationOps} />
            <div className="grid grid-cols-3 gap-2">
              <Info label="Webhooks" value={`${integrationOps.data?.webhooks.length ?? 0}`} />
              <Info label="Retry" value={`${integrationOps.data?.retry_queue.length ?? 0}`} />
              <Info label="SFTP" value={labelize(integrationOps.data?.sftp.status ?? "not_configured")} />
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2">
              <ActionButton
                busy={activeAction === "configure-webhook"}
                disabled={busy}
                icon={<Network size={14} />}
                onClick={configureCoreWebhook}
              >
                Hook
              </ActionButton>
              <ActionButton
                busy={activeAction === "queue-sftp"}
                disabled={busy || !selectedCase}
                icon={<Upload size={14} />}
                onClick={queueSftpBatch}
              >
                SFTP
              </ActionButton>
              <ActionButton
                busy={activeAction === "retry-integration"}
                disabled={busy || !retryEvent}
                icon={<RefreshCcw size={14} />}
                onClick={retryIntegration}
              >
                Retry
              </ActionButton>
            </div>
            <div className="mt-3 max-h-44 space-y-2 overflow-auto pr-1">
              {(integrationOps.data?.webhooks ?? []).slice(-2).map((hook) => (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs" key={hook.key}>
                  <div className="flex items-start justify-between gap-2">
                    <p className="truncate font-semibold">{hook.key}</p>
                    <StatusBadge status={hook.status} />
                  </div>
                  <p className="mt-1 truncate font-mono text-slate-500">{hook.url}</p>
                </div>
              ))}
              {(integrationOps.data?.retry_queue ?? []).slice(0, 2).map((event) => (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs" key={event.event_id}>
                  <div className="flex items-start justify-between gap-2">
                    <p className="truncate font-mono font-semibold text-amber-900">{event.event_id}</p>
                    <StatusBadge status={event.status} />
                  </div>
                  <p className="mt-1 truncate text-amber-800">{event.last_error ?? event.target ?? event.mode}</p>
                </div>
              ))}
            </div>
          </Panel>
          ) : null}

          {section === "integrations" ? (
          <Panel title="Export Payload" icon={<Database size={16} />}>
            <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-xl bg-slate-950 p-3 font-mono text-xs leading-relaxed text-slate-50">
              {exportJson || "{ }"}
            </pre>
          </Panel>
          ) : null}

          {["admin", "cases", "review"].includes(section) ? (
          <Panel title="Audit" icon={<History size={16} />}>
            <ol className="space-y-2">
              {(selectedCase?.audit_events ?? []).slice(0, 8).map((event, index) => (
                <li className="grid grid-cols-[86px_1fr] gap-3 text-xs" key={`${event.action}-${index}`}>
                  <span className="font-mono text-slate-500">{formatDate(event.created_at)}</span>
                  <span className="min-w-0">
                    <span className="block truncate font-semibold">{event.action}</span>
                    <span className="block truncate text-slate-500">{event.actor}</span>
                  </span>
                </li>
              ))}
              {!selectedCase?.audit_events.length ? <p className="text-sm text-slate-500">No audit events</p> : null}
            </ol>
          </Panel>
          ) : null}
        </aside>
        ) : null}
      </div>
    </main>
  );
}

function Panel({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white shadow-[var(--shadow-soft)]">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <h2 className="text-sm font-bold text-slate-950">{title}</h2>
        <span className="rounded-xl bg-indigo-50 p-2 text-indigo-600">{icon}</span>
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

function FieldLabel({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{label}</span>
      {children}
    </label>
  );
}

function Kpi({ icon, label, value }: { icon: ReactNode; label: string; value: number }) {
  return (
    <div className="group rounded-2xl border border-slate-200 bg-white p-4 shadow-[var(--shadow-soft)] hover:-translate-y-1 hover:shadow-[var(--shadow-lift)]">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-slate-500">{label}</span>
        <span className="rounded-xl bg-indigo-50 p-2 text-indigo-600 group-hover:bg-indigo-100">{icon}</span>
      </div>
      <p className="mt-3 font-mono text-3xl font-bold text-slate-950">{value}</p>
    </div>
  );
}

function Pill({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <span className="inline-flex h-10 max-w-full items-center gap-2 rounded-full border border-slate-200 bg-white px-4 font-semibold text-slate-700 shadow-[var(--shadow-soft)]">
      <span className="shrink-0 text-indigo-600">{icon}</span>
      <span className="truncate">{label}</span>
    </span>
  );
}

function ModuleSwitcher({ activeHref, activeSection }: { activeHref: string; activeSection: WorkspaceSection }) {
  return (
    <nav className="rounded-[1.35rem] border border-slate-200 bg-white/95 p-2 shadow-[var(--shadow-soft)]">
      <div className="flex gap-2 overflow-x-auto">
        {workspaceNav.map((item) => {
          const active = item.href === activeHref || item.section === activeSection;
          return (
            <Link
              className={`group inline-flex min-w-fit items-center gap-2 rounded-full px-4 py-2.5 text-sm font-bold ${
                active
                  ? "bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-[var(--shadow-button)]"
                  : "text-slate-600 hover:-translate-y-0.5 hover:bg-indigo-50 hover:text-indigo-700"
              }`}
              href={item.href}
              key={item.section}
            >
              <span className={active ? "text-white" : "text-slate-400 group-hover:text-indigo-600"}>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs font-bold uppercase tracking-[0.1em] text-slate-500">{label}</p>
      <p className="mt-1 truncate text-sm font-bold text-slate-950">{value}</p>
    </div>
  );
}

function InfoBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs">
      <p className="font-bold text-slate-900">{label}</p>
      <p className="mt-1 truncate font-mono text-slate-500">{value}</p>
    </div>
  );
}

function SectionLabel({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <div className="mb-2 flex items-center gap-2 text-sm font-bold text-slate-950">
      <span className="rounded-lg bg-indigo-50 p-1.5 text-indigo-600">{icon}</span>
      <span>{label}</span>
    </div>
  );
}

function StatusBadge({ status }: { status?: string }) {
  return (
    <span className={`inline-flex max-w-full items-center rounded-lg border px-2.5 py-1 text-xs font-bold ${statusTone(status)}`}>
      <span className="truncate">{labelize(status)}</span>
    </span>
  );
}

function ResourceError<T>({ resource }: { resource: ResourceState<T> }) {
  if (resource.status !== "error") {
    return null;
  }
  return (
    <div className="mb-3 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs font-medium text-amber-800">
      <AlertTriangle className="mt-0.5 shrink-0" size={14} />
      <p className="min-w-0 break-words">{resource.error}</p>
    </div>
  );
}

function ActionButton({
  busy,
  children,
  icon,
  tone = "secondary",
  ...props
}: {
  busy?: boolean;
  children: ReactNode;
  icon: ReactNode;
  tone?: "primary" | "secondary";
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const toneClass =
    tone === "primary"
      ? "border-indigo-600 bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-[var(--shadow-button)] hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)]"
      : "border-slate-200 bg-white text-slate-700 hover:-translate-y-0.5 hover:border-indigo-200 hover:bg-slate-50 hover:text-indigo-700 hover:shadow-[var(--shadow-soft)]";
  return (
    <button
      {...props}
      className={`inline-flex h-10 min-w-0 items-center justify-center gap-2 rounded-full border px-3 text-xs font-bold disabled:cursor-not-allowed disabled:opacity-60 ${toneClass} ${
        props.className ?? ""
      }`}
      disabled={props.disabled || busy}
      type={props.type ?? "button"}
    >
      {busy ? <Loader2 className="shrink-0 animate-spin" size={14} /> : <span className="shrink-0">{icon}</span>}
      <span className="truncate">{children}</span>
    </button>
  );
}
