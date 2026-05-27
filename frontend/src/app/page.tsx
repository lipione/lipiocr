"use client";

import {
  Activity,
  AlertTriangle,
  BadgeCheck,
  Building2,
  ClipboardCheck,
  Download,
  FileStack,
  FileSearch,
  FileText,
  Fingerprint,
  KeyRound,
  Link2,
  Loader2,
  Network,
  Play,
  Plug,
  Plus,
  RefreshCcw,
  Save,
  ShieldCheck,
  SplitSquareHorizontal,
  Upload,
  Zap,
} from "lucide-react";
import { type Dispatch, FormEvent, type SetStateAction, useCallback, useEffect, useMemo, useState } from "react";

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
};

type AiHealth = {
  provider: string;
  model: string;
  api_base: string;
  enabled: boolean;
};

type IntegrationManifest = {
  modes: string[];
  events: string[];
  core_endpoints: string[];
};

type LoadStatus = "idle" | "loading" | "ready" | "error";

type ResourceState<T> = {
  status: LoadStatus;
  data: T | null;
  error: string | null;
  updatedAt: string | null;
};

type IntelligenceChecklistItem = {
  id?: string;
  key?: string;
  label?: string;
  title?: string;
  status?: string;
  severity?: string;
  message?: string;
  evidence?: string;
  category?: string;
  confidence?: number;
};

type CaseIntelligence = {
  summary?: string;
  completeness_score?: number;
  risk_score?: number;
  checklist?: IntelligenceChecklistItem[];
  policy_signals?: IntelligenceChecklistItem[];
  next_actions?: string[];
};

type PacketDocument = {
  id?: string;
  filename?: string;
  document_type?: string;
  declared_document_type?: string;
  status?: string;
  confidence?: number;
  pages?: number[];
  page_count?: number;
  reason?: string;
};

type SplitPreviewResponse = {
  packet_id?: string;
  documents?: PacketDocument[];
  pages?: PacketDocument[];
  warnings?: string[];
};

type ClassificationResponse = {
  documents?: PacketDocument[];
  classifications?: PacketDocument[];
  summary?: string;
  case?: KycCase;
};

type ValidationResponse = {
  status?: string;
  findings?: ValidationFinding[];
  warnings?: string[];
  case?: KycCase;
};

type VerificationResponse = {
  run_id?: string;
  status?: string;
  decision?: string;
  score?: number;
  checks?: IntelligenceChecklistItem[];
  findings?: ValidationFinding[];
  case?: KycCase;
};

type IntegrationProfile = {
  key?: string;
  profile_key?: string;
  name?: string;
  label?: string;
  category?: string;
  status?: string;
  adapter_status?: string;
  mode?: string;
  destination?: string;
  description?: string;
  configured?: boolean;
};

type IntegrationProfilesResponse =
  | IntegrationProfile[]
  | {
      profiles?: IntegrationProfile[];
      adapters?: IntegrationProfile[];
      items?: IntegrationProfile[];
    };

type WebhookTestResponse = {
  status?: string;
  profile_key?: string;
  event_id?: string;
  message?: string;
};

type EmbeddedReviewLinkResponse = {
  url?: string;
  review_url?: string;
  expires_at?: string;
};

type TenantAdminResponse = {
  institution_name?: string;
  tenant_key?: string;
  environment?: string;
  data_residency?: string;
  retention_days?: number;
  features?: string[];
};

type RbacResponse = {
  roles?: { name?: string; users?: number; permissions?: string[] }[];
  maker_checker?: boolean;
  active_users?: number;
};

type AuditIntegrityResponse = {
  status?: string;
  last_verified_at?: string;
  ledger_head?: string;
  gaps?: number;
  immutable_events?: number;
};

type ReviewQueueResponse =
  | {
      items?: { case_id?: string; applicant_name?: string; status?: string; risk_level?: string; age_minutes?: number }[];
      counts?: Record<string, number>;
    }
  | { case_id?: string; applicant_name?: string; status?: string; risk_level?: string; age_minutes?: number }[];

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

const statusClasses: Record<CaseStatus, string> = {
  created: "border-zinc-300 bg-zinc-50 text-zinc-700",
  processing: "border-blue-200 bg-blue-50 text-blue-700",
  review_required: "border-amber-200 bg-amber-50 text-amber-700",
  approved: "border-emerald-200 bg-emerald-50 text-emerald-700",
  rejected: "border-rose-200 bg-rose-50 text-rose-700",
  exported: "border-teal-200 bg-teal-50 text-teal-700",
};

const defaultIntegrationProfiles: IntegrationProfile[] = [
  {
    key: "core_banking",
    name: "Core Banking CBS",
    category: "Core ledger",
    status: "not_configured",
    mode: "export_profile",
    destination: "CBS customer master",
  },
  {
    key: "mobile_banking",
    name: "Mobile Banking KYC",
    category: "Digital channel",
    status: "not_configured",
    mode: "webhook",
    destination: "Wallet and mobile app onboarding",
  },
  {
    key: "nrb_goaml",
    name: "NRB / FIU Screening",
    category: "Regulatory",
    status: "not_configured",
    mode: "verification",
    destination: "Sanctions and adverse media checks",
  },
  {
    key: "document_vault",
    name: "Document Vault Archive",
    category: "Records",
    status: "not_configured",
    mode: "embedded_review",
    destination: "Retention and audit evidence",
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

function labelize(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

function compactId(value: string) {
  return value.length > 18 ? `${value.slice(0, 8)}...${value.slice(-6)}` : value;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function pct(value: number) {
  return `${Math.round(value * 100)}%`;
}

function optionalPct(value?: number) {
  if (typeof value !== "number") {
    return "n/a";
  }
  return value <= 1 ? pct(value) : `${Math.round(value)}%`;
}

function statusTone(status?: string) {
  const normalized = (status ?? "unknown").toLowerCase();
  if (["approved", "configured", "ready", "passed", "complete", "verified", "ok", "healthy"].includes(normalized)) {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (["review_required", "warning", "pending", "partial", "not_configured", "not configured"].includes(normalized)) {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  if (["rejected", "failed", "error", "blocked", "missing"].includes(normalized)) {
    return "border-rose-200 bg-rose-50 text-rose-700";
  }
  if (["processing", "running", "loading"].includes(normalized)) {
    return "border-blue-200 bg-blue-50 text-blue-700";
  }
  return "border-zinc-200 bg-zinc-50 text-zinc-700";
}

function normalizeProfiles(data: IntegrationProfilesResponse | null) {
  if (!data) {
    return [];
  }
  if (Array.isArray(data)) {
    return data;
  }
  return data.profiles ?? data.adapters ?? data.items ?? [];
}

function profileKey(profile: IntegrationProfile) {
  return profile.key ?? profile.profile_key ?? "profile";
}

function profileName(profile: IntegrationProfile) {
  return profile.name ?? profile.label ?? labelize(profileKey(profile));
}

function profileStatus(profile: IntegrationProfile) {
  if (profile.status) {
    return profile.status;
  }
  if (profile.adapter_status) {
    return profile.adapter_status;
  }
  return profile.configured === false ? "not_configured" : "configured";
}

function packetDocuments(data: SplitPreviewResponse | ClassificationResponse | null) {
  if (!data) {
    return [];
  }
  return data.documents ?? ("classifications" in data ? data.classifications : undefined) ?? ("pages" in data ? data.pages : undefined) ?? [];
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

function blockStyle(block: OcrBlock, page: OcrPage) {
  const [x1, y1, x2, y2] = block.bbox;
  return {
    left: `${(x1 / page.width) * 100}%`,
    top: `${(y1 / page.height) * 100}%`,
    width: `${((x2 - x1) / page.width) * 100}%`,
    height: `${((y2 - y1) / page.height) * 100}%`,
  };
}

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    const message = detail ? `${response.status} ${detail.slice(0, 120)}` : `${response.status} ${response.statusText}`;
    throw new Error(message.trim());
  }
  return (await response.json()) as T;
}

export default function Home() {
  const [cases, setCases] = useState<KycCase[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [caseType, setCaseType] = useState<CaseType>("individual_kyc");
  const [applicantName, setApplicantName] = useState("Sita Sharma");
  const [customerRef, setCustomerRef] = useState("CBS-1001");
  const [documentType, setDocumentType] = useState<DocumentType>("citizenship");
  const [file, setFile] = useState<File | null>(null);
  const [aiHealth, setAiHealth] = useState<AiHealth | null>(null);
  const [manifest, setManifest] = useState<IntegrationManifest | null>(null);
  const [message, setMessage] = useState("Starting");
  const [busy, setBusy] = useState(false);
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [exportJson, setExportJson] = useState("");
  const [profileKeySelection, setProfileKeySelection] = useState("core_banking");
  const [intelligence, setIntelligence] = useState<ResourceState<CaseIntelligence>>(() =>
    emptyResource<CaseIntelligence>(),
  );
  const [splitPreview, setSplitPreview] = useState<ResourceState<SplitPreviewResponse>>(() =>
    emptyResource<SplitPreviewResponse>(),
  );
  const [classification, setClassification] = useState<ResourceState<ClassificationResponse>>(() =>
    emptyResource<ClassificationResponse>(),
  );
  const [validationResult, setValidationResult] = useState<ResourceState<ValidationResponse>>(() =>
    emptyResource<ValidationResponse>(),
  );
  const [verification, setVerification] = useState<ResourceState<VerificationResponse>>(() =>
    emptyResource<VerificationResponse>(),
  );
  const [profiles, setProfiles] = useState<ResourceState<IntegrationProfilesResponse>>(() =>
    emptyResource<IntegrationProfilesResponse>(),
  );
  const [webhookTest, setWebhookTest] = useState<ResourceState<WebhookTestResponse>>(() =>
    emptyResource<WebhookTestResponse>(),
  );
  const [reviewLink, setReviewLink] = useState<ResourceState<EmbeddedReviewLinkResponse>>(() =>
    emptyResource<EmbeddedReviewLinkResponse>(),
  );
  const [profileExport, setProfileExport] = useState<ResourceState<unknown>>(() => emptyResource<unknown>());
  const [tenant, setTenant] = useState<ResourceState<TenantAdminResponse>>(() =>
    emptyResource<TenantAdminResponse>(),
  );
  const [rbac, setRbac] = useState<ResourceState<RbacResponse>>(() => emptyResource<RbacResponse>());
  const [auditIntegrity, setAuditIntegrity] = useState<ResourceState<AuditIntegrityResponse>>(() =>
    emptyResource<AuditIntegrityResponse>(),
  );
  const [reviewQueue, setReviewQueue] = useState<ResourceState<ReviewQueueResponse>>(() =>
    emptyResource<ReviewQueueResponse>(),
  );

  const selectedCase = useMemo(
    () => cases.find((item) => item.id === selectedId) ?? cases[0] ?? null,
    [cases, selectedId],
  );

  const selectedDocument = selectedCase?.documents[0] ?? null;
  const selectedPage = selectedDocument?.pages[0] ?? null;
  const configuredProfiles = useMemo(() => normalizeProfiles(profiles.data), [profiles.data]);
  const visibleProfiles = configuredProfiles.length ? configuredProfiles : defaultIntegrationProfiles;
  const selectedProfile =
    visibleProfiles.find((profile) => profileKey(profile) === profileKeySelection) ?? visibleProfiles[0];
  const queueItems = useMemo(() => {
    if (!reviewQueue.data) {
      return [];
    }
    return Array.isArray(reviewQueue.data) ? reviewQueue.data : reviewQueue.data.items ?? [];
  }, [reviewQueue.data]);

  const metrics = useMemo(
    () => ({
      cases: cases.length,
      review: cases.filter((item) => item.status === "review_required").length,
      approved: cases.filter((item) => item.status === "approved").length,
      documents: cases.reduce((total, item) => total + item.documents.length, 0),
      highRisk: cases.filter((item) => item.risk_level?.toLowerCase() === "high").length,
    }),
    [cases],
  );

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

  const loadPlatformContext = useCallback(async () => {
    setProfiles((current) => loadingResource(current));
    setTenant((current) => loadingResource(current));
    setRbac((current) => loadingResource(current));
    setAuditIntegrity((current) => loadingResource(current));
    setReviewQueue((current) => loadingResource(current));

    await Promise.allSettled([
      apiJson<IntegrationProfilesResponse>("/api/integrations/profiles", { cache: "no-store" })
        .then((data) => setProfiles(readyResource(data)))
        .catch((error) =>
          setProfiles((current) => failedResource(current, error, "Integration profiles unavailable")),
        ),
      apiJson<TenantAdminResponse>("/api/admin/tenant", { cache: "no-store" })
        .then((data) => setTenant(readyResource(data)))
        .catch((error) => setTenant((current) => failedResource(current, error, "Tenant controls unavailable"))),
      apiJson<RbacResponse>("/api/admin/rbac", { cache: "no-store" })
        .then((data) => setRbac(readyResource(data)))
        .catch((error) => setRbac((current) => failedResource(current, error, "RBAC unavailable"))),
      apiJson<AuditIntegrityResponse>("/api/admin/audit-integrity", { cache: "no-store" })
        .then((data) => setAuditIntegrity(readyResource(data)))
        .catch((error) =>
          setAuditIntegrity((current) => failedResource(current, error, "Audit integrity unavailable")),
        ),
      apiJson<ReviewQueueResponse>("/api/review/queue", { cache: "no-store" })
        .then((data) => setReviewQueue(readyResource(data)))
        .catch((error) => setReviewQueue((current) => failedResource(current, error, "Review queue unavailable"))),
    ]);
  }, []);

  const loadCaseIntelligence = useCallback(async (caseId: string) => {
    setIntelligence((current) => loadingResource(current));
    try {
      const data = await apiJson<CaseIntelligence>(`/api/cases/${caseId}/intelligence`, { cache: "no-store" });
      setIntelligence(readyResource(data));
    } catch (error) {
      setIntelligence((current) => failedResource(current, error, "Checklist intelligence unavailable"));
    }
  }, []);

  const refresh = useCallback(async () => {
    setMessage("Syncing");
    try {
      const data = await apiJson<KycCase[]>("/api/cases", { cache: "no-store" });
      setCases(data);
      setSelectedId((current) => current ?? data[0]?.id ?? null);
      setMessage("Connected");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Backend unavailable");
    }

    const [aiResult, manifestResult] = await Promise.allSettled([
      apiJson<AiHealth>("/api/ai/health", { cache: "no-store" }),
      apiJson<IntegrationManifest>("/api/integrations/manifest", { cache: "no-store" }),
    ]);
    if (aiResult.status === "fulfilled") {
      setAiHealth(aiResult.value);
    }
    if (manifestResult.status === "fulfilled") {
      setManifest(manifestResult.value);
    }
    void loadPlatformContext();
  }, [loadPlatformContext]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refresh();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  useEffect(() => {
    if (!visibleProfiles.some((profile) => profileKey(profile) === profileKeySelection)) {
      setProfileKeySelection(profileKey(visibleProfiles[0]));
    }
  }, [profileKeySelection, visibleProfiles]);

  useEffect(() => {
    const caseId = selectedCase?.id;
    setSplitPreview(emptyResource<SplitPreviewResponse>());
    setClassification(emptyResource<ClassificationResponse>());
    setValidationResult(emptyResource<ValidationResponse>());
    setVerification(emptyResource<VerificationResponse>());
    setWebhookTest(emptyResource<WebhookTestResponse>());
    setReviewLink(emptyResource<EmbeddedReviewLinkResponse>());
    setProfileExport(emptyResource<unknown>());
    if (!caseId) {
      setIntelligence(emptyResource<CaseIntelligence>());
      return;
    }
    void loadCaseIntelligence(caseId);
  }, [loadCaseIntelligence, selectedCase?.id]);

  async function runCaseEndpoint<T>(
    actionKey: string,
    label: string,
    path: string,
    setter: Dispatch<SetStateAction<ResourceState<T>>>,
    body: Record<string, unknown> = {},
  ) {
    if (!selectedCase) {
      return null;
    }
    setBusy(true);
    setActiveAction(actionKey);
    setMessage(label);
    setter((current) => loadingResource(current));
    try {
      const data = await apiJson<T>(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setter(readyResource(data));
      mergeCaseFromPayload(data);
      void loadPlatformContext();
      setMessage(`${label} complete`);
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

  async function createCase(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setBusy(true);
    setMessage("Creating case");
    try {
      const response = await fetch(`${API_BASE}/api/cases`, {
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
      if (!response.ok) {
        throw new Error("Case creation failed");
      }
      const created = (await response.json()) as KycCase;
      setCases((current) => [created, ...current]);
      setSelectedId(created.id);
      setExportJson("");
      setMessage("Case created");
      void loadPlatformContext();
      return created;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Case creation failed");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function uploadDocument(targetCase: KycCase, uploadFile: File) {
    setBusy(true);
    setMessage("Processing document");
    setExportJson("");
    try {
      const form = new FormData();
      form.append("declared_document_type", documentType);
      form.append("file", uploadFile);
      const response = await fetch(`${API_BASE}/api/cases/${targetCase.id}/documents`, {
        method: "POST",
        body: form,
      });
      if (!response.ok) {
        throw new Error("Document processing failed");
      }
      const updated = (await response.json()) as KycCase;
      setCases((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setSelectedId(updated.id);
      setMessage("Document processed");
      void loadCaseIntelligence(updated.id);
      void loadPlatformContext();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Document processing failed");
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
    const target = selectedCase ?? (await createCase());
    if (!target) {
      return;
    }
    const sample = new File(
      ["Name: Sita Sharma\nCitizenship No: 27-01-78-12345\nMobile: 9841000000"],
      "nepal-individual-kyc-citizenship.txt",
      { type: "text/plain" },
    );
    await uploadDocument(target, sample);
  }

  async function approveCase() {
    if (!selectedCase) {
      return;
    }
    setBusy(true);
    setMessage("Approving");
    try {
      const response = await fetch(`${API_BASE}/api/cases/${selectedCase.id}/review`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reviewer: "checker.one",
          decision: "approve",
          field_updates: {},
          note: "Maker-checker review complete.",
        }),
      });
      if (!response.ok) {
        throw new Error("Approval failed");
      }
      const updated = (await response.json()) as KycCase;
      setCases((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setMessage("Approved");
      void loadPlatformContext();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Approval failed");
    } finally {
      setBusy(false);
    }
  }

  async function exportCase() {
    if (!selectedCase) {
      return;
    }
    setBusy(true);
    setActiveAction("export-json");
    setMessage("Exporting");
    try {
      const response = await fetch(`${API_BASE}/api/cases/${selectedCase.id}/export`);
      if (!response.ok) {
        throw new Error("Export failed");
      }
      setExportJson(JSON.stringify(await response.json(), null, 2));
      setMessage("Export ready");
      void loadPlatformContext();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Export failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function runSplitPreview() {
    if (!selectedCase) {
      return;
    }
    await runCaseEndpoint<SplitPreviewResponse>(
      "split-preview",
      "Building split preview",
      `/api/cases/${selectedCase.id}/split-preview`,
      setSplitPreview,
      { profile_key: profileKeySelection },
    );
  }

  async function runClassify() {
    if (!selectedCase) {
      return;
    }
    await runCaseEndpoint<ClassificationResponse>(
      "classify",
      "Classifying packet",
      `/api/cases/${selectedCase.id}/classify`,
      setClassification,
      { institution_id: selectedCase.institution_id, branch_code: selectedCase.branch_code ?? "KTM-001" },
    );
  }

  async function runValidate() {
    if (!selectedCase) {
      return;
    }
    await runCaseEndpoint<ValidationResponse>(
      "validate",
      "Running validation",
      `/api/cases/${selectedCase.id}/validate`,
      setValidationResult,
      { policy: "nepal_financial_institution_kyc" },
    );
  }

  async function runVerification() {
    if (!selectedCase) {
      return;
    }
    await runCaseEndpoint<VerificationResponse>(
      "verification",
      "Running advanced verification",
      `/api/cases/${selectedCase.id}/verification/run`,
      setVerification,
      { profile_key: profileKeySelection, jurisdiction: "NP", branch_code: selectedCase.branch_code ?? "KTM-001" },
    );
  }

  async function testWebhook() {
    setBusy(true);
    setActiveAction("webhook-test");
    setMessage("Testing webhook");
    setWebhookTest((current) => loadingResource(current));
    try {
      const data = await apiJson<WebhookTestResponse>("/api/integrations/webhook/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: selectedCase?.id,
          profile_key: profileKeySelection,
          event: "kyc.case.review_required",
        }),
      });
      setWebhookTest(readyResource(data));
      setMessage("Webhook test complete");
    } catch (error) {
      setWebhookTest((current) => failedResource(current, error, "Webhook test failed"));
      setMessage(error instanceof Error ? error.message : "Webhook test failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function createEmbeddedReviewLink() {
    if (!selectedCase) {
      return;
    }
    setBusy(true);
    setActiveAction("review-link");
    setMessage("Creating review link");
    setReviewLink((current) => loadingResource(current));
    try {
      const data = await apiJson<EmbeddedReviewLinkResponse>(
        `/api/cases/${selectedCase.id}/embedded-review-link`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile_key: profileKeySelection, role: "checker" }),
        },
      );
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

  async function exportProfile() {
    if (!selectedCase) {
      return;
    }
    setBusy(true);
    setActiveAction("export-profile");
    setMessage("Exporting profile");
    setProfileExport((current) => loadingResource(current));
    try {
      const data = await apiJson<unknown>(
        `/api/cases/${selectedCase.id}/export-profile/${encodeURIComponent(profileKeySelection)}`,
        { cache: "no-store" },
      );
      setProfileExport(readyResource(data));
      setExportJson(JSON.stringify(data, null, 2));
      setMessage("Export profile ready");
    } catch (error) {
      setProfileExport((current) => failedResource(current, error, "Export profile failed"));
      setMessage(error instanceof Error ? error.message : "Export profile failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  const checklistItems = intelligence.data?.checklist ?? [];
  const policySignals = intelligence.data?.policy_signals ?? [];
  const splitDocuments = packetDocuments(splitPreview.data);
  const classifiedDocuments = packetDocuments(classification.data);
  const validationFindings = validationResult.data?.findings ?? selectedCase?.validation_findings ?? [];
  const verificationChecks = verification.data?.checks ?? [];
  const reviewUrl = reviewLink.data?.url ?? reviewLink.data?.review_url ?? "";
  const selectedProfileStatus = selectedProfile ? profileStatus(selectedProfile) : "not_configured";
  const reviewCounts = reviewQueue.data && !Array.isArray(reviewQueue.data) ? reviewQueue.data.counts : undefined;

  return (
    <main className="min-h-screen bg-[#f6f7f8] text-zinc-950">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-[1540px] flex-col gap-4 px-4 py-4 sm:px-6 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">LipiOCR Enterprise</p>
            <h1 className="mt-1 text-2xl font-semibold tracking-normal">
              Nepal FI KYC Command Center
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="inline-flex h-9 items-center gap-2 rounded-md border border-zinc-200 bg-zinc-50 px-3 font-medium text-zinc-700">
              <Activity size={16} />
              {message}
            </span>
            <span className="inline-flex h-9 max-w-full items-center gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 font-medium text-blue-700">
              <Network size={16} />
              <span className="truncate">{aiHealth?.model ?? "gemma-4-26b-4bit"}</span>
            </span>
            <button
              className="inline-flex h-9 items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 font-medium hover:bg-zinc-50"
              onClick={refresh}
              type="button"
            >
              <RefreshCcw size={16} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1540px] gap-4 px-4 py-4 sm:px-6 xl:grid-cols-[340px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <section className="rounded-lg border border-zinc-200 bg-white p-4">
            <form className="space-y-3" onSubmit={createCase}>
              <div className="grid grid-cols-1 gap-3">
                <FieldLabel label="Case Type">
                  <select
                    className="h-10 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm outline-none focus:border-teal-600"
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
                    className="h-10 w-full rounded-md border border-zinc-300 px-3 text-sm outline-none focus:border-teal-600"
                    value={applicantName}
                    onChange={(event) => setApplicantName(event.target.value)}
                  />
                </FieldLabel>
                <FieldLabel label="CBS / LOS Ref">
                  <input
                    className="h-10 w-full rounded-md border border-zinc-300 px-3 font-mono text-sm outline-none focus:border-teal-600"
                    value={customerRef}
                    onChange={(event) => setCustomerRef(event.target.value)}
                  />
                </FieldLabel>
              </div>
              <button
                className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-teal-700 px-3 text-sm font-semibold text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={busy}
                type="submit"
              >
                {busy ? <Loader2 className="animate-spin" size={16} /> : <Plus size={16} />}
                Create Case
              </button>
            </form>
          </section>

          <section className="rounded-lg border border-zinc-200 bg-white p-4">
            <form className="space-y-3" onSubmit={handleUpload}>
              <FieldLabel label="Document Type">
                <select
                  className="h-10 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm outline-none focus:border-teal-600"
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
              <label className="flex min-h-24 cursor-pointer flex-col items-center justify-center rounded-md border border-dashed border-zinc-300 bg-zinc-50 px-3 text-center hover:border-teal-500">
                <Upload className="mb-2 text-teal-700" size={22} />
                <span className="max-w-full truncate text-sm font-medium">
                  {file?.name ?? "Choose document"}
                </span>
                <input
                  className="sr-only"
                  type="file"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-zinc-900 px-3 text-sm font-semibold text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={busy || !file || !selectedCase}
                  type="submit"
                >
                  <Upload size={16} />
                  Upload
                </button>
                <button
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-zinc-300 bg-white px-3 text-sm font-semibold hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={busy}
                  onClick={runSamplePacket}
                  type="button"
                >
                  <FileText size={16} />
                  Sample
                </button>
              </div>
            </form>
          </section>

          <section className="rounded-lg border border-zinc-200 bg-white">
            <div className="border-b border-zinc-200 px-4 py-3">
              <h2 className="text-sm font-semibold">KYC Cases</h2>
            </div>
            <div className="max-h-[520px] overflow-auto p-2">
              {cases.length === 0 ? (
                <p className="p-3 text-sm text-zinc-500">No cases yet</p>
              ) : (
                cases.map((item) => (
                  <button
                    className={`mb-2 block w-full rounded-md border p-3 text-left hover:border-teal-500 ${
                      selectedCase?.id === item.id
                        ? "border-teal-600 bg-teal-50"
                        : "border-zinc-200 bg-white"
                    }`}
                    key={item.id}
                    onClick={() => {
                      setSelectedId(item.id);
                      setExportJson("");
                    }}
                    type="button"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold">{item.applicant_name}</p>
                        <p className="mt-1 truncate font-mono text-xs text-zinc-500">
                          {item.integration_ref ?? item.id}
                        </p>
                      </div>
                      <span
                        className={`shrink-0 rounded-md border px-2 py-1 text-xs font-semibold ${statusClasses[item.status]}`}
                      >
                        {labelize(item.status)}
                      </span>
                    </div>
                    <div className="mt-3 flex items-center justify-between text-xs text-zinc-500">
                      <span>{labelize(item.case_type)}</span>
                      <span>{item.documents.length} docs</span>
                    </div>
                  </button>
                ))
              )}
            </div>
          </section>
        </aside>

        <section className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <Metric icon={<Building2 size={18} />} label="Cases" value={metrics.cases} />
            <Metric icon={<ClipboardCheck size={18} />} label="Review" value={metrics.review} />
            <Metric icon={<AlertTriangle size={18} />} label="High Risk" value={metrics.highRisk} />
            <Metric icon={<BadgeCheck size={18} />} label="Approved" value={metrics.approved} />
            <Metric icon={<FileSearch size={18} />} label="Documents" value={metrics.documents} />
          </div>

          <div className="grid gap-4 2xl:grid-cols-[minmax(0,1.25fr)_minmax(410px,0.75fr)]">
            <section className="rounded-lg border border-zinc-200 bg-white">
              <div className="flex flex-col gap-3 border-b border-zinc-200 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0">
                  <h2 className="text-sm font-semibold">
                    {selectedCase ? selectedCase.applicant_name : "No active case"}
                  </h2>
                  <p className="mt-1 truncate font-mono text-xs text-zinc-500">
                    {selectedCase?.id ?? "Create a case or run the sample packet"}
                  </p>
                </div>
                {selectedCase ? (
                  <span
                    className={`w-fit rounded-md border px-2.5 py-1 text-xs font-semibold ${statusClasses[selectedCase.status]}`}
                  >
                    {labelize(selectedCase.status)} · {selectedCase.risk_level.toUpperCase()}
                  </span>
                ) : null}
              </div>

              {selectedCase ? (
                <div className="grid gap-4 p-4 xl:grid-cols-[minmax(360px,0.9fr)_minmax(420px,1.1fr)]">
                  <div className="space-y-3">
                    <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
                      <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
                        <Info label="Type" value={labelize(selectedCase.case_type)} />
                        <Info label="Institution" value={selectedCase.institution_id} />
                        <Info label="Branch" value={selectedCase.branch_code ?? "KTM-001"} />
                        <Info label="Ref" value={selectedCase.integration_ref ?? "None"} />
                      </div>
                    </div>

                    <div className="relative aspect-[0.72] overflow-hidden rounded-md border border-zinc-300 bg-[#fbfaf7] shadow-inner">
                      <div className="absolute inset-x-5 top-5 flex items-start justify-between border-b border-zinc-300 pb-3">
                        <div className="min-w-0">
                          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-zinc-500">
                            {selectedDocument ? labelize(selectedDocument.document_type) : "Document Packet"}
                          </p>
                          <p className="mt-1 truncate text-lg font-semibold">
                            {selectedDocument?.filename ?? "No document uploaded"}
                          </p>
                        </div>
                        <FileText className="shrink-0 text-teal-700" size={26} />
                      </div>
                      {selectedPage ? (
                        selectedPage.blocks.map((block, index) => (
                          <div
                            className="absolute overflow-hidden rounded-sm border border-teal-600 bg-teal-100/70 px-1.5 py-1 text-[10px] font-semibold leading-tight text-teal-950"
                            key={`${block.text}-${index}`}
                            style={blockStyle(block, selectedPage)}
                            title={block.text}
                          >
                            <span className="block truncate">{block.text}</span>
                            <span className="block font-mono">{pct(block.confidence)}</span>
                          </div>
                        ))
                      ) : (
                        <div className="absolute inset-x-6 top-28 text-sm text-zinc-500">
                          Upload a document to see OCR evidence blocks.
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="min-w-0 overflow-hidden rounded-md border border-zinc-200">
                    <div className="grid grid-cols-[1fr_92px_120px] border-b border-zinc-200 bg-zinc-50 px-3 py-2 text-xs font-semibold uppercase tracking-[0.1em] text-zinc-500">
                      <span>Field</span>
                      <span>Confidence</span>
                      <span>Evidence</span>
                    </div>
                    <div className="max-h-[650px] overflow-auto">
                      {selectedCase.extracted_fields.length === 0 ? (
                        <p className="p-4 text-sm text-zinc-500">No extracted fields yet</p>
                      ) : (
                        selectedCase.extracted_fields.map((field) => (
                          <div
                            className="grid gap-2 border-b border-zinc-100 p-3 last:border-b-0 sm:grid-cols-[1fr_92px_120px]"
                            key={`${field.key}-${field.document_id ?? ""}`}
                          >
                            <div className="min-w-0">
                              <p className="text-xs font-semibold text-zinc-500">{field.label}</p>
                              <p className="mt-1 truncate text-sm font-medium">{field.value || "Unclear"}</p>
                              <p className="mt-1 truncate text-xs text-zinc-500">
                                {field.validation_message}
                              </p>
                            </div>
                            <div className="flex items-center">
                              <span className="rounded-md bg-zinc-100 px-2 py-1 font-mono text-xs">
                                {pct(field.confidence)}
                              </span>
                            </div>
                            <div className="min-w-0 text-xs">
                              <p className="font-mono text-zinc-600">p{field.evidence.source_page}</p>
                              <p className="truncate text-zinc-500">{field.evidence.evidence_text}</p>
                              <p className="mt-1 truncate text-teal-700">{field.extracted_by}</p>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                    <div className="flex flex-col gap-2 border-t border-zinc-200 bg-zinc-50 p-3 sm:flex-row sm:justify-end">
                      <button
                        className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-zinc-300 bg-white px-3 text-sm font-semibold hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={busy || !selectedCase}
                        type="button"
                      >
                        <Save size={16} />
                        Save
                      </button>
                      <button
                        className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-teal-700 px-3 text-sm font-semibold text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={busy || !selectedCase}
                        onClick={approveCase}
                        type="button"
                      >
                        {busy ? <Loader2 className="animate-spin" size={16} /> : <ShieldCheck size={16} />}
                        Approve
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-8 text-sm text-zinc-500">Create a case to begin.</div>
              )}
            </section>

            <section className="space-y-4">
              <Panel title="Checklist Intelligence" icon={<Fingerprint size={16} />}>
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-2">
                    <Info label="Complete" value={optionalPct(intelligence.data?.completeness_score)} />
                    <Info label="Risk" value={optionalPct(intelligence.data?.risk_score)} />
                    <Info
                      label="Updated"
                      value={intelligence.updatedAt ? formatDate(intelligence.updatedAt) : intelligence.status}
                    />
                  </div>
                  <ResourceError resource={intelligence} />
                  <p className="rounded-md border border-zinc-200 bg-zinc-50 p-3 text-sm leading-relaxed text-zinc-700">
                    {intelligence.data?.summary ??
                      (intelligence.status === "loading"
                        ? "Loading KYC checklist intelligence."
                        : "Checklist intelligence has not returned for this case.")}
                  </p>
                  <div className="max-h-56 space-y-2 overflow-auto pr-1">
                    {checklistItems.length ? (
                      checklistItems.map((item, index) => (
                        <div
                          className="grid grid-cols-[1fr_auto] gap-3 rounded-md border border-zinc-200 p-3 text-xs"
                          key={item.id ?? item.key ?? `${item.title ?? item.label}-${index}`}
                        >
                          <div className="min-w-0">
                            <p className="truncate font-semibold">{item.title ?? item.label ?? item.key}</p>
                            <p className="mt-1 truncate text-zinc-500">{item.message ?? item.evidence ?? "Ready"}</p>
                          </div>
                          <StatusBadge status={item.status ?? item.severity} />
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-zinc-500">No checklist items yet</p>
                    )}
                  </div>
                  {policySignals.length ? (
                    <div className="grid gap-2 sm:grid-cols-2">
                      {policySignals.slice(0, 4).map((signal, index) => (
                        <div className="min-w-0 rounded-md bg-zinc-50 p-2 text-xs" key={`${signal.key ?? signal.label}-${index}`}>
                          <p className="truncate font-semibold">{signal.label ?? signal.title ?? signal.key}</p>
                          <p className="mt-1 truncate text-zinc-500">{signal.message ?? signal.category ?? "Policy signal"}</p>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              </Panel>

              <Panel title="Document Packet / Classification" icon={<FileStack size={16} />}>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-2">
                    <ActionButton
                      busy={activeAction === "split-preview"}
                      disabled={busy || !selectedCase}
                      icon={<SplitSquareHorizontal size={14} />}
                      onClick={runSplitPreview}
                    >
                      Split Preview
                    </ActionButton>
                    <ActionButton
                      busy={activeAction === "classify"}
                      disabled={busy || !selectedCase}
                      icon={<FileSearch size={14} />}
                      onClick={runClassify}
                      tone="primary"
                    >
                      Classify
                    </ActionButton>
                  </div>
                  <ResourceError resource={splitPreview} />
                  <ResourceError resource={classification} />
                  <div className="space-y-2">
                    {(selectedCase?.documents ?? []).map((document) => (
                      <div
                        className="grid grid-cols-[1fr_auto] gap-3 rounded-md border border-zinc-200 p-3 text-xs"
                        key={document.id}
                      >
                        <div className="min-w-0">
                          <p className="truncate font-semibold">{document.filename}</p>
                          <p className="mt-1 truncate text-zinc-500">
                            {labelize(document.declared_document_type)} declared · {document.page_count} pages
                          </p>
                        </div>
                        <StatusBadge status={document.document_type} />
                      </div>
                    ))}
                    {!selectedCase?.documents.length ? <p className="text-sm text-zinc-500">No packet documents yet</p> : null}
                  </div>
                  {splitDocuments.length || classifiedDocuments.length ? (
                    <div className="grid gap-2">
                      {[...splitDocuments, ...classifiedDocuments].slice(0, 6).map((document, index) => (
                        <div
                          className="grid grid-cols-[1fr_72px] gap-3 rounded-md bg-zinc-50 p-2 text-xs"
                          key={`${document.id ?? document.filename ?? document.document_type}-${index}`}
                        >
                          <div className="min-w-0">
                            <p className="truncate font-semibold">
                              {labelize(document.document_type ?? document.declared_document_type ?? "unknown")}
                            </p>
                            <p className="mt-1 truncate text-zinc-500">
                              {document.filename ?? document.reason ?? `${document.page_count ?? document.pages?.length ?? 0} pages`}
                            </p>
                          </div>
                          <span className="self-center rounded-md bg-white px-2 py-1 text-center font-mono">
                            {optionalPct(document.confidence)}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              </Panel>

              <Panel title="Advanced Verification" icon={<Zap size={16} />}>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-2">
                    <ActionButton
                      busy={activeAction === "validate"}
                      disabled={busy || !selectedCase}
                      icon={<ClipboardCheck size={14} />}
                      onClick={runValidate}
                    >
                      Validate
                    </ActionButton>
                    <ActionButton
                      busy={activeAction === "verification"}
                      disabled={busy || !selectedCase}
                      icon={<Play size={14} />}
                      onClick={runVerification}
                      tone="primary"
                    >
                      Verify
                    </ActionButton>
                  </div>
                  <ResourceError resource={validationResult} />
                  <ResourceError resource={verification} />
                  <div className="grid grid-cols-3 gap-2">
                    <Info label="Decision" value={verification.data?.decision ?? validationResult.data?.status ?? "pending"} />
                    <Info label="Score" value={optionalPct(verification.data?.score)} />
                    <Info label="Run" value={verification.data?.run_id ? compactId(verification.data.run_id) : "none"} />
                  </div>
                  <div className="max-h-52 space-y-2 overflow-auto pr-1">
                    {validationFindings.length ? (
                      validationFindings.map((finding, index) => (
                        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs" key={`${finding.code}-${index}`}>
                          <div className="flex items-start justify-between gap-2">
                            <p className="min-w-0 truncate font-semibold text-amber-900">{finding.code}</p>
                            <StatusBadge status={finding.severity} />
                          </div>
                          <p className="mt-1 truncate text-amber-800">{finding.message}</p>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-zinc-500">No validation findings yet</p>
                    )}
                    {verificationChecks.map((check, index) => (
                      <div className="grid grid-cols-[1fr_auto] gap-3 rounded-md border border-zinc-200 p-3 text-xs" key={`${check.key ?? check.label}-${index}`}>
                        <div className="min-w-0">
                          <p className="truncate font-semibold">{check.label ?? check.title ?? check.key}</p>
                          <p className="mt-1 truncate text-zinc-500">{check.message ?? check.evidence ?? "Verification check"}</p>
                        </div>
                        <StatusBadge status={check.status ?? check.severity} />
                      </div>
                    ))}
                  </div>
                </div>
              </Panel>

              <Panel title="Integrations" icon={<Plug size={16} />}>
                <div className="space-y-3">
                  <ResourceError resource={profiles} />
                  <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
                    <select
                      className="h-9 min-w-0 rounded-md border border-zinc-300 bg-white px-2 text-xs font-semibold outline-none focus:border-teal-600"
                      value={profileKeySelection}
                      onChange={(event) => setProfileKeySelection(event.target.value)}
                    >
                      {visibleProfiles.map((profile) => (
                        <option key={profileKey(profile)} value={profileKey(profile)}>
                          {profileName(profile)}
                        </option>
                      ))}
                    </select>
                    <StatusBadge status={selectedProfileStatus} />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Info label="Modes" value={manifest?.modes.slice(0, 3).join(", ") ?? "loading"} />
                    <Info label="Events" value={manifest?.events.slice(0, 3).join(", ") ?? "loading"} />
                  </div>
                  <div className="max-h-48 space-y-2 overflow-auto pr-1">
                    {visibleProfiles.map((profile) => (
                      <div className="grid grid-cols-[1fr_auto] gap-3 rounded-md border border-zinc-200 p-3 text-xs" key={profileKey(profile)}>
                        <div className="min-w-0">
                          <p className="truncate font-semibold">{profileName(profile)}</p>
                          <p className="mt-1 truncate text-zinc-500">
                            {profile.category ?? profile.mode ?? "External adapter"} · {profile.destination ?? "Nepal FI channel"}
                          </p>
                        </div>
                        <StatusBadge status={profileStatus(profile)} />
                      </div>
                    ))}
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <ActionButton
                      busy={activeAction === "webhook-test"}
                      disabled={busy}
                      icon={<Network size={14} />}
                      onClick={testWebhook}
                    >
                      Webhook
                    </ActionButton>
                    <ActionButton
                      busy={activeAction === "review-link"}
                      disabled={busy || !selectedCase}
                      icon={<Link2 size={14} />}
                      onClick={createEmbeddedReviewLink}
                    >
                      Review Link
                    </ActionButton>
                    <ActionButton
                      busy={activeAction === "export-profile"}
                      disabled={busy || !selectedCase}
                      icon={<Download size={14} />}
                      onClick={exportProfile}
                      tone="primary"
                    >
                      Export
                    </ActionButton>
                  </div>
                  <ResourceError resource={webhookTest} />
                  <ResourceError resource={reviewLink} />
                  <ResourceError resource={profileExport} />
                  {webhookTest.data ? (
                    <div className="rounded-md bg-zinc-50 p-2 text-xs">
                      <span className="font-semibold">{webhookTest.data.status ?? "webhook_result"}</span>
                      <span className="ml-2 font-mono text-zinc-500">{webhookTest.data.event_id ?? webhookTest.data.message}</span>
                    </div>
                  ) : null}
                  {reviewUrl ? (
                    <div className="rounded-md bg-zinc-950 p-2 font-mono text-xs text-zinc-50">
                      <p className="truncate">{reviewUrl}</p>
                      <p className="mt-1 text-zinc-400">{reviewLink.data?.expires_at ?? "no expiry returned"}</p>
                    </div>
                  ) : null}
                </div>
              </Panel>

              <Panel title="Enterprise Controls" icon={<KeyRound size={16} />}>
                <div className="space-y-3">
                  <ResourceError resource={tenant} />
                  <ResourceError resource={rbac} />
                  <ResourceError resource={auditIntegrity} />
                  <ResourceError resource={reviewQueue} />
                  <div className="grid grid-cols-2 gap-2">
                    <Info label="Tenant" value={tenant.data?.institution_name ?? tenant.data?.tenant_key ?? "Nepal FI demo"} />
                    <Info label="Residency" value={tenant.data?.data_residency ?? "NP"} />
                    <Info label="RBAC Users" value={`${rbac.data?.active_users ?? 0}`} />
                    <Info label="Retention" value={tenant.data?.retention_days ? `${tenant.data.retention_days} days` : "policy"} />
                  </div>
                  <div className="grid grid-cols-[1fr_auto] gap-3 rounded-md border border-zinc-200 p-3 text-xs">
                    <div className="min-w-0">
                      <p className="truncate font-semibold">Maker-checker controls</p>
                      <p className="mt-1 truncate text-zinc-500">
                        {(rbac.data?.roles ?? []).map((role) => role.name).filter(Boolean).slice(0, 3).join(", ") || "Roles pending"}
                      </p>
                    </div>
                    <StatusBadge status={rbac.data?.maker_checker ? "configured" : "not_configured"} />
                  </div>
                  <div className="grid grid-cols-[1fr_auto] gap-3 rounded-md border border-zinc-200 p-3 text-xs">
                    <div className="min-w-0">
                      <p className="truncate font-semibold">Audit integrity ledger</p>
                      <p className="mt-1 truncate font-mono text-zinc-500">
                        {auditIntegrity.data?.ledger_head ? compactId(auditIntegrity.data.ledger_head) : "ledger pending"}
                      </p>
                    </div>
                    <StatusBadge status={auditIntegrity.data?.status ?? "unknown"} />
                  </div>
                  {reviewCounts ? (
                    <div className="grid grid-cols-3 gap-2">
                      {Object.entries(reviewCounts)
                        .slice(0, 3)
                        .map(([key, value]) => (
                          <div className="rounded-md bg-zinc-50 p-2 text-xs" key={key}>
                            <p className="truncate font-semibold">{labelize(key)}</p>
                            <p className="mt-1 font-mono text-lg">{value}</p>
                          </div>
                        ))}
                    </div>
                  ) : null}
                  <div className="max-h-36 space-y-2 overflow-auto pr-1">
                    {queueItems.slice(0, 4).map((item) => (
                      <div className="grid grid-cols-[1fr_auto] gap-3 rounded-md bg-zinc-50 p-2 text-xs" key={item.case_id ?? item.applicant_name}>
                        <div className="min-w-0">
                          <p className="truncate font-semibold">{item.applicant_name ?? item.case_id}</p>
                          <p className="mt-1 truncate text-zinc-500">{item.age_minutes ?? 0} min · {item.risk_level ?? "risk pending"}</p>
                        </div>
                        <StatusBadge status={item.status} />
                      </div>
                    ))}
                    {!queueItems.length ? <p className="text-sm text-zinc-500">No queue items returned</p> : null}
                  </div>
                  {selectedCase?.audit_events.length ? (
                    <ol className="space-y-2 border-t border-zinc-200 pt-3">
                      {selectedCase.audit_events.slice(0, 4).map((event, index) => (
                        <li className="grid grid-cols-[82px_1fr] gap-3 text-xs" key={`${event.action}-${index}`}>
                          <span className="font-mono text-zinc-500">{formatDate(event.created_at)}</span>
                          <span className="min-w-0">
                            <span className="block truncate font-semibold">{event.action}</span>
                            <span className="block truncate text-zinc-500">{event.actor}</span>
                          </span>
                        </li>
                      ))}
                    </ol>
                  ) : null}
                </div>
              </Panel>

              <Panel
                title="Export Payload"
                icon={
                  <ActionButton
                    busy={activeAction === "export-json"}
                    disabled={busy || !selectedCase}
                    icon={<Download size={14} />}
                    onClick={exportCase}
                  >
                    JSON
                  </ActionButton>
                }
              >
                <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-md bg-zinc-950 p-3 font-mono text-xs leading-relaxed text-zinc-50">
                  {exportJson || "{ }"}
                </pre>
              </Panel>
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}

function FieldLabel({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-zinc-500">
        {label}
      </span>
      {children}
    </label>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-zinc-600">{label}</span>
        <span className="text-teal-700">{icon}</span>
      </div>
      <p className="mt-3 font-mono text-3xl font-semibold">{value}</p>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-semibold uppercase tracking-[0.1em] text-zinc-500">{label}</p>
      <p className="mt-1 truncate text-sm font-medium text-zinc-900">{value}</p>
    </div>
  );
}

function StatusBadge({ status }: { status?: string }) {
  return (
    <span className={`inline-flex max-w-full items-center rounded-md border px-2 py-1 text-xs font-semibold ${statusTone(status)}`}>
      <span className="truncate">{labelize(status ?? "unknown")}</span>
    </span>
  );
}

function ResourceError<T>({ resource }: { resource: ResourceState<T> }) {
  if (resource.status !== "error") {
    return null;
  }
  return (
    <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
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
  children: React.ReactNode;
  icon: React.ReactNode;
  tone?: "primary" | "secondary";
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const toneClass =
    tone === "primary"
      ? "border-teal-700 bg-teal-700 text-white hover:bg-teal-800"
      : "border-zinc-300 bg-white text-zinc-900 hover:bg-zinc-50";
  return (
    <button
      {...props}
      className={`inline-flex h-9 min-w-0 items-center justify-center gap-2 rounded-md border px-2.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60 ${toneClass} ${
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

function Panel({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white">
      <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3">
        <h2 className="text-sm font-semibold">{title}</h2>
        <span className="text-zinc-500">{icon}</span>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}
