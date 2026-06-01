"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  Archive,
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
  MapPin,
  Network,
  Pencil,
  Play,
  Plug,
  Plus,
  RefreshCcw,
  Route,
  SearchCheck,
  ShieldAlert,
  ShieldCheck,
  SplitSquareHorizontal,
  Trash2,
  Upload,
  Workflow,
} from "lucide-react";
import { FormEvent, PointerEvent as ReactPointerEvent, ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { createOperatorSession, loadOperatorSession, logoutOperatorSession, type OperatorPrincipal, type OperatorSessionRequest } from "../lib/auth-client";
import {
  createAddressEvidence,
  deleteAddressEvidence,
  importAddressEvidence,
  searchAddressEvidence,
  updateAddressEvidence,
  type AddressEvidenceRecord,
} from "../lib/address-evidence";
import { API_BASE, apiJson, isUnauthorized, listJobs, retryJob } from "../lib/api-client";
import { computeTemplateDragBbox, type TemplateDragMode } from "../lib/template-canvas";
import { AccuracyReport } from "./analytics/accuracy-report";
import { LoginPanel } from "./auth/login-panel";
import { LipiOcrLogo } from "./brand/lipiocr-logo";
import { TemplateStudioPanel } from "./templates/template-studio";

import type {
  AccuracyAnalytics,
  AiHealth,
  AssignmentResponse,
  CaseIntelligence,
  CaseType,
  ClassificationResponse,
  CommentResponse,
  CorrectionResponse,
  DocumentLane,
  DocumentRecord,
  DocumentType,
  EmbeddedReviewLinkResponse,
  ExportProfileResponse,
  ExtractedField,
  FieldGroup,
  IntegrationOperations,
  IntegrationProfilesResponse,
  JobEnvelope,
  KycCase,
  OcrBlock,
  OcrPage,
  OcrPipelineProfile,
  OperationsDashboard,
  PlatformStatus,
  PreviewOverlayMode,
  ProcessingJob,
  ResourceState,
  ReviewWorkbench,
  SplitPreviewResponse,
  TemplateDraft,
  TemplateDragState,
  TemplateProfileField,
  TemplateProfilePage,
  TemplateStudio,
  ValidationResponse,
  VerificationAdapter,
  VerificationAdapterRunResponse,
  VerificationAdaptersResponse,
  VerificationResponse,
  WebhookTestResponse,
  WorkspaceSection,
} from "../types/workspace";

const caseTypes: { value: CaseType; label: string }[] = [
  { value: "individual_kyc", label: "Individual KYC" },
  { value: "business_kyb", label: "Business KYB" },
  { value: "loan_onboarding", label: "Loan Onboarding" },
  { value: "document_digitization", label: "Digitization" },
];

const previewOverlayModes: { value: PreviewOverlayMode; label: string; icon: ReactNode }[] = [
  { value: "clean", label: "Original", icon: <FileText size={14} /> },
  { value: "evidence", label: "Highlights", icon: <Eye size={14} /> },
];

const workspaceNav: { section: WorkspaceSection; href: string; label: string; description: string; icon: ReactNode }[] = [
  {
    section: "command",
    href: "/dashboard",
    label: "Dashboard",
    description: "Workload, review status, and ready-to-export files",
    icon: <Gauge size={16} />,
  },
  {
    section: "cases",
    href: "/cases",
    label: "Applications",
    description: "Customer onboarding files and status",
    icon: <Boxes size={16} />,
  },
  {
    section: "documents",
    href: "/documents",
    label: "Documents",
    description: "Upload documents and correct extracted data",
    icon: <FileSearch size={16} />,
  },
  {
    section: "review",
    href: "/review",
    label: "Review",
    description: "Human checks, corrections, and approvals",
    icon: <ClipboardCheck size={16} />,
  },
  {
    section: "verification",
    href: "/verification",
    label: "Verify",
    description: "Identity and compliance checks",
    icon: <LockKeyhole size={16} />,
  },
  {
    section: "templates",
    href: "/templates",
    label: "Formats",
    description: "Reusable document formats and validation rules",
    icon: <FileCog size={16} />,
  },
  {
    section: "integrations",
    href: "/integrations",
    label: "Connect",
    description: "Export and handoff to institution systems",
    icon: <Plug size={16} />,
  },
  {
    section: "analytics",
    href: "/analytics",
    label: "Reports",
    description: "Accuracy, corrections, and throughput",
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

function fieldKeyFromLabel(value: string) {
  const key = value
    .trim()
    .toLowerCase()
    .replace(/['"]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return key || "custom_field";
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
    return "border-cyan-200 bg-cyan-50 text-cyan-700";
  }
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function hasUsableBbox(bbox?: number[] | null): bbox is [number, number, number, number] {
  return Boolean(bbox && bbox.length === 4 && bbox.every((value) => Number.isFinite(value)));
}

function pageAspectRatio(page?: Pick<OcrPage, "width" | "height"> | null) {
  if (!page?.width || !page.height) {
    return "0.72";
  }
  return `${page.width} / ${page.height}`;
}

function bboxStyle(bbox: number[], page: Pick<OcrPage, "width" | "height">) {
  const [x1, y1, x2, y2] = bbox;
  return {
    height: `${((y2 - y1) / page.height) * 100}%`,
    left: `${(x1 / page.width) * 100}%`,
    top: `${(y1 / page.height) * 100}%`,
    width: `${((x2 - x1) / page.width) * 100}%`,
  };
}

function blockStyle(block: OcrBlock, page: OcrPage) {
  return bboxStyle(block.bbox, page);
}

function evidenceOverlayTone(field: ExtractedField) {
  const source = `${field.source ?? ""} ${field.extracted_by ?? ""}`.toLowerCase();
  if (source.includes("handwriting")) {
    return "border-amber-500/70 bg-amber-300/5 shadow-[0_0_0_1px_rgba(245,158,11,0.08)]";
  }
  if (source.includes("gemma")) {
    return "border-teal-500/70 bg-teal-300/5 shadow-[0_0_0_1px_rgba(14,165,168,0.08)]";
  }
  return "border-emerald-500/70 bg-emerald-300/5 shadow-[0_0_0_1px_rgba(16,185,129,0.08)]";
}

function fieldEditorKey(field: ExtractedField) {
  return `${field.document_id ?? field.evidence.document_id ?? "case"}:${field.key}`;
}

function normalizedConfidence(field: ExtractedField) {
  return field.confidence > 1 ? field.confidence / 100 : field.confidence;
}

function extractionSourceLabel(field: ExtractedField) {
  const source = `${field.source ?? ""} ${field.extracted_by ?? ""}`.toLowerCase();
  if (source.includes("reviewer")) {
    return "Reviewer";
  }
  if (source.includes("handwriting")) {
    return "LipiCore handwriting";
  }
  if (source.includes("full-page") || source.includes("ocr")) {
    return "LipiCore OCR";
  }
  return "LipiCore";
}

function providerLabel(provider: { key: string; label: string }) {
  if (provider.key === "gemma_vision") {
    return "LipiCore Vision";
  }
  if (provider.key === "mock") {
    return "LipiCore Demo";
  }
  return "LipiCore OCR";
}

function providerBestFor(provider: { key: string; best_for: string }) {
  if (provider.key === "gemma_vision") {
    return "Printed and handwritten Nepali/English source text";
  }
  if (provider.key === "mock") {
    return "Sample documents and offline walkthroughs";
  }
  return "Printed document recognition";
}

function sourceImageUrl(imageUri?: string | null) {
  if (!imageUri) {
    return null;
  }
  if (/^https?:\/\//i.test(imageUri)) {
    return imageUri;
  }
  return `${API_BASE}${imageUri}`;
}

function packetDocuments(data: SplitPreviewResponse | ClassificationResponse | null) {
  if (!data) {
    return [];
  }
  return "segments" in data ? data.segments : data.classifications;
}

function matchesSearch(value: string, query: string) {
  const normalizedQuery = query.trim().toLowerCase();
  return !normalizedQuery || value.toLowerCase().includes(normalizedQuery);
}

function fieldGroupMeta(field: ExtractedField): Omit<FieldGroup, "fields"> {
  const text = `${field.key} ${field.label}`.toLowerCase();
  if (field.key.startsWith("ocr_line_")) {
    return { key: "raw", label: "Raw OCR", description: "Unmapped text retained for traceability." };
  }
  if (/(name|citizenship|passport|license|pan|national|father|mother|guardian|spouse|photo|signature)/.test(text)) {
    return { key: "identity", label: "Identity", description: "Person, document, and family identity fields." };
  }
  if (/(address|district|ward|municipality|province|zone|street|house|ठेगाना|जिल्ला|वडा)/.test(text)) {
    return { key: "address", label: "Address", description: "Nepali and English address components." };
  }
  if (/(date|dob|birth|issue|expiry|मिति|जन्म|ad|bs)$/.test(text) || /(_ad|_bs)$/.test(field.key)) {
    return { key: "dates", label: "Dates", description: "AD/BS date values and derived calendar pairs." };
  }
  if (/(mobile|phone|email|contact|telephone)/.test(text)) {
    return { key: "contact", label: "Contact", description: "Phone, mobile, and email values." };
  }
  if (/(bank|account|cheque|dp|boid|client|branch|issuer)/.test(text)) {
    return { key: "banking", label: "Banking", description: "Bank account, branch, DP, client, and cheque fields." };
  }
  if (/(amount|unit|price|share|balance|deposit|fee|rs|रकम|कित्ता)/.test(text)) {
    return { key: "amounts", label: "Amounts", description: "Money, units, prices, and share quantities." };
  }
  return { key: "other", label: "Other", description: "Document-specific fields that need review." };
}

function groupExtractionFields(fields: ExtractedField[]): FieldGroup[] {
  const order = ["identity", "address", "dates", "contact", "banking", "amounts", "other", "raw"];
  const groups = new Map<string, FieldGroup>();
  for (const field of fields) {
    const meta = fieldGroupMeta(field);
    const existing = groups.get(meta.key);
    if (existing) {
      existing.fields.push(field);
    } else {
      groups.set(meta.key, { ...meta, fields: [field] });
    }
  }
  return [...groups.values()].sort((left, right) => order.indexOf(left.key) - order.indexOf(right.key));
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

function isJobEnvelope(value: unknown): value is JobEnvelope {
  return Boolean(value && typeof value === "object" && "job_id" in value && "status_url" in value);
}

export function EnterpriseWorkspace({ section }: { section: WorkspaceSection }) {
  const pathname = usePathname();
  const templateCanvasRef = useRef<HTMLDivElement | null>(null);
  const [cases, setCases] = useState<KycCase[]>([]);
  const [standaloneDocuments, setStandaloneDocuments] = useState<DocumentRecord[]>([]);
  const [documentLane, setDocumentLane] = useState<DocumentLane>("application");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [caseType, setCaseType] = useState<CaseType>("individual_kyc");
  const [applicantName, setApplicantName] = useState("Sita Sharma");
  const [customerRef, setCustomerRef] = useState("APP-1001");
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [selectedStandaloneDocumentId, setSelectedStandaloneDocumentId] = useState<string | null>(null);
  const [previewOverlayMode, setPreviewOverlayMode] = useState<PreviewOverlayMode>("clean");
  const [fieldDrafts, setFieldDrafts] = useState<Record<string, string>>({});
  const [manualFieldLabel, setManualFieldLabel] = useState("");
  const [manualFieldKey, setManualFieldKey] = useState("");
  const [manualFieldValue, setManualFieldValue] = useState("");
  const [templateName, setTemplateName] = useState("New Document Template");
  const [templateDocumentType, setTemplateDocumentType] = useState<DocumentType>("unknown");
  const [templateFiles, setTemplateFiles] = useState<File[]>([]);
  const [templateDraft, setTemplateDraft] = useState<TemplateDraft | null>(null);
  const [selectedTemplatePageNumber, setSelectedTemplatePageNumber] = useState(1);
  const [selectedTemplateFieldId, setSelectedTemplateFieldId] = useState<string | null>(null);
  const [templateDrag, setTemplateDrag] = useState<TemplateDragState | null>(null);
  const [addressQuery, setAddressQuery] = useState("Samakhusi");
  const [addressResults, setAddressResults] = useState<AddressEvidenceRecord[]>([]);
  const [addressFilters, setAddressFilters] = useState({ district: "", localLevel: "", ward: "" });
  const [addressEditingId, setAddressEditingId] = useState<string | null>(null);
  const [addressImportDraft, setAddressImportDraft] = useState("");
  const [addressDraft, setAddressDraft] = useState({
    district_name: "Kathmandu",
    local_level_name: "Kathmandu Metropolitan City",
    ward: "26",
    kind: "area_or_tole",
    name_en: "",
    name_np: "",
    aliases_en: "",
    aliases_np: "",
  });
  const [applicationSearch, setApplicationSearch] = useState("");
  const [documentSearch, setDocumentSearch] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [standaloneFiles, setStandaloneFiles] = useState<File[]>([]);
  const [message, setMessage] = useState("Starting");
  const [operatorSession, setOperatorSession] = useState<OperatorPrincipal | null>(null);
  const [accessRequired, setAccessRequired] = useState(false);
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
  const [jobQueue, setJobQueue] = useState<ResourceState<ProcessingJob[]>>(() => emptyResource<ProcessingJob[]>());
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
  const selectedApplicationDocument = selectedCase
    ? selectedCase.documents.find((document) => document.id === selectedDocumentId) ??
      selectedCase.documents[0] ??
      null
    : null;
  const selectedStandaloneDocument =
    standaloneDocuments.find((document) => document.id === selectedStandaloneDocumentId) ?? standaloneDocuments[0] ?? null;
  const selectedDocument =
    section === "documents" && documentLane === "standalone" ? selectedStandaloneDocument : selectedApplicationDocument;
  const selectedPage = selectedDocument?.pages[0] ?? null;
  const selectedImageSrc = sourceImageUrl(selectedPage?.image_uri);
  const selectedDocumentFields =
    section === "documents" && documentLane === "standalone"
      ? selectedStandaloneDocument?.fields ?? []
      : selectedCase && selectedDocument
        ? selectedCase.extracted_fields.filter((field) => field.document_id === selectedDocument.id)
        : [];
  const visibleExtractionFields =
    selectedDocumentFields.length > 0
      ? selectedDocumentFields
      : section === "documents" && documentLane === "standalone"
        ? []
        : selectedCase?.extracted_fields ?? [];
  const fieldDraftSeed = JSON.stringify(
    visibleExtractionFields.map((field) => [fieldEditorKey(field), field.value ?? ""]),
  );
  const primaryExtractionFields = visibleExtractionFields.filter((field) => !field.key.startsWith("ocr_line_"));
  const rawOcrFields = visibleExtractionFields.filter((field) => field.key.startsWith("ocr_line_"));
  const editableExtractionFields = primaryExtractionFields.length ? primaryExtractionFields : visibleExtractionFields;
  const pendingFieldUpdates = editableExtractionFields.reduce<Record<string, string>>((updates, field) => {
    const draftValue = fieldDrafts[fieldEditorKey(field)] ?? field.value ?? "";
    if (draftValue !== (field.value ?? "")) {
      updates[field.key] = draftValue;
    }
    return updates;
  }, {});
  const manualFieldResolvedKey = fieldKeyFromLabel(manualFieldKey || manualFieldLabel);
  const pendingCorrectionCount = Object.keys(pendingFieldUpdates).length;
  const groupedEditableFields = groupExtractionFields(editableExtractionFields);
  const needsReviewCount = editableExtractionFields.filter(
    (field) => normalizedConfidence(field) < 0.9 || !["valid", "ok", "passed"].includes(field.validation_status.toLowerCase()),
  ).length;
  const filteredCases = cases.filter((item) =>
    matchesSearch(`${item.applicant_name} ${item.integration_ref ?? ""} ${item.id} ${item.status}`, applicationSearch),
  );
  const filteredStandaloneDocuments = standaloneDocuments.filter((document) =>
    matchesSearch(`${document.filename} ${document.document_type} ${document.status} ${document.id}`, documentSearch),
  );
  const selectedPageEvidenceFields =
    selectedPage && selectedDocument
      ? visibleExtractionFields.filter(
          (field) =>
            field.evidence.source_page === selectedPage.page_number &&
            (field.document_id ?? field.evidence.document_id) === selectedDocument.id &&
            !field.key.startsWith("ocr_line_") &&
            hasUsableBbox(field.evidence.bbox),
        )
      : [];
  const selectedPageBlockCount = selectedPage?.blocks.length ?? 0;
  const selectedPageHandwritingBlockCount =
    selectedPage?.blocks.filter((block) => block.block_type === "handwriting").length ?? 0;
  const selectedTemplate = templateStudio.data?.templates.find(
    (template) => template.document_type === selectedDocument?.document_type,
  );
  const requiredTemplateFields = selectedTemplate?.required_fields ?? [];
  const extractedFieldKeys = new Set(visibleExtractionFields.map((field) => field.key));
  const templateCoverage = requiredTemplateFields.length
    ? requiredTemplateFields.filter((fieldKey) => extractedFieldKeys.has(fieldKey)).length / requiredTemplateFields.length
    : visibleExtractionFields.length
      ? 1
      : 0;
  const extractionConfidence = visibleExtractionFields.length
    ? visibleExtractionFields.reduce((total, field) => total + field.confidence, 0) / visibleExtractionFields.length
    : 0;
  const exportProfiles = useMemo(
    () => profiles.data?.export_profiles ?? ["cbs_standard", "los_loan", "aml_case"],
    [profiles.data?.export_profiles],
  );
  const readinessScore = intelligence.data?.readiness_score ?? 0;
  const validationFindings = validation.data?.findings ?? selectedCase?.validation_findings ?? [];
  const packetResults = [...packetDocuments(splitPreview.data), ...packetDocuments(classification.data)].slice(0, 6);
  const embeddedDocumentIntelligence = selectedDocument?.intelligence ?? null;
  const selectedDocumentIntelligence =
    embeddedDocumentIntelligence ??
    intelligence.data?.document_intelligence?.find((item) => item.document_id === selectedDocument?.id) ??
    intelligence.data?.document_intelligence?.[0] ??
    null;
  const canonicalFieldRows = Object.entries(selectedDocumentIntelligence?.canonical_fields ?? {}).slice(0, 8);
  const semanticChecks = selectedDocumentIntelligence?.cross_checks ?? intelligence.data?.cross_checks ?? [];
  const languagePairs = selectedDocumentIntelligence?.language_pairs ?? intelligence.data?.language_pairs ?? [];
  const confidenceRepairs = selectedDocumentIntelligence?.confidence_repairs ?? intelligence.data?.confidence_repairs ?? [];
  const entityReconciliations = intelligence.data?.entity_reconciliation ?? [];
  const selectedDocumentVariant = selectedDocumentIntelligence?.document_variant ?? null;
  const selectedDocumentAssets = selectedDocument?.assets ?? selectedDocumentIntelligence?.assets ?? [];
  const selectedDocumentSections = selectedDocument?.document_sections ?? selectedDocumentIntelligence?.document_sections ?? [];
  const selectedEvidenceLedger = selectedDocument?.evidence_ledger ?? selectedDocumentIntelligence?.evidence_ledger ?? [];
  const selectedEntityRecords = selectedDocumentIntelligence?.entity_records ?? [];
  const selectedLocationResolutions = selectedDocumentIntelligence?.location_resolutions ?? [];
  const missingFieldCount = editableExtractionFields.filter((field) => !String(field.value ?? "").trim()).length;
  const lowConfidenceCount = editableExtractionFields.filter((field) => normalizedConfidence(field) < 0.8).length;
  const exportReadinessStatus =
    missingFieldCount > 0
      ? "Missing values"
      : pendingCorrectionCount > 0
        ? "Unsaved edits"
        : needsReviewCount > 0
          ? "Needs review"
          : "Ready";
  const exportReadinessTone =
    exportReadinessStatus === "Ready"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : exportReadinessStatus === "Unsaved edits"
        ? "border-cyan-200 bg-cyan-50 text-cyan-900"
        : "border-amber-200 bg-amber-50 text-amber-800";
  const selectedFileLabel =
    selectedFiles.length === 0
      ? "Choose documents"
      : selectedFiles.length === 1
        ? selectedFiles[0].name
        : `${selectedFiles.length} documents selected`;
  const standaloneFileLabel =
    standaloneFiles.length === 0
      ? "Choose documents"
      : standaloneFiles.length === 1
        ? standaloneFiles[0].name
        : `${standaloneFiles.length} documents selected`;
  const reviewField =
    selectedCase?.extracted_fields.find((field) => field.key.includes("citizenship")) ??
    selectedCase?.extracted_fields[0] ??
    null;
  const reviewFieldDraftValue = reviewField ? (fieldDrafts[fieldEditorKey(reviewField)] ?? reviewField.value ?? "") : "";
  const operatorActor = operatorSession?.user_id ?? "operator";
  const accuracyRows = Object.entries(accuracy.data?.field_accuracy ?? {}).slice(0, 5);
  const retryEvent = integrationOps.data?.retry_queue[0] ?? null;
  const isDocumentWorkspace = section === "documents";
  const showCaseIntake = section === "cases";
  const showDocumentIntake = false;
  const showWorkQueue = ["command", "cases", "documents", "review", "verification", "integrations"].includes(section);
  const showLeftRail = !isDocumentWorkspace && (showCaseIntake || showDocumentIntake || showWorkQueue);
  const showRightRail =
    !isDocumentWorkspace && ["command", "cases", "documents", "review", "verification", "integrations", "admin"].includes(section);
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
    documents: cases.reduce((total, item) => total + item.documents.length, 0) + standaloneDocuments.length,
    review_required: cases.filter((item) => item.status === "review_required").length,
    approved: cases.filter((item) => item.status === "approved").length,
    exceptions: cases.filter((item) => item.risk_level === "high").length,
  };
  const recentJobs = jobQueue.data?.slice(0, 4) ?? [];
  const selectedTemplatePage =
    templateDraft?.pages.find((page) => page.page_number === selectedTemplatePageNumber) ?? templateDraft?.pages[0] ?? null;
  const selectedTemplateField =
    templateDraft?.fields.find((field) => field.id === selectedTemplateFieldId) ??
    templateDraft?.fields.find((field) => field.page_number === selectedTemplatePage?.page_number) ??
    templateDraft?.fields[0] ??
    null;
  const selectedTemplatePageFields = templateDraft?.fields.filter((field) => field.page_number === selectedTemplatePage?.page_number) ?? [];
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

  useEffect(() => {
    setManualFieldLabel("");
    setManualFieldKey("");
    setManualFieldValue("");
  }, [selectedDocument?.id]);

  useEffect(() => {
    const activeDrag = templateDrag;
    const activePage = selectedTemplatePage;
    if (!activeDrag || !activePage) {
      return undefined;
    }
    const dragState: TemplateDragState = activeDrag;
    const pageState: TemplateProfilePage = activePage;

    function handlePointerMove(event: PointerEvent) {
      const canvasRect = templateCanvasRef.current?.getBoundingClientRect();
      if (!canvasRect) {
        return;
      }
      const nextBbox = computeTemplateDragBbox({
        mode: dragState.mode,
        startBbox: dragState.startBbox,
        startClientX: dragState.startClientX,
        startClientY: dragState.startClientY,
        clientX: event.clientX,
        clientY: event.clientY,
        page: pageState,
        canvasRect,
      });

      setTemplateDraft((current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          fields: current.fields.map((field) =>
            field.id === dragState.fieldId ? { ...field, bbox: nextBbox } : field,
          ),
        };
      });
    }

    function handlePointerUp() {
      setTemplateDrag(null);
    }

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, [selectedTemplatePage, templateDrag]);

  const handleApiFailure = useCallback((error: unknown, fallbackMessage: string) => {
    if (isUnauthorized(error)) {
      setAccessRequired(true);
      setOperatorSession(null);
      setMessage("Operator session required");
      return;
    }
    setMessage(error instanceof Error ? error.message : fallbackMessage);
  }, []);

  const markAccessFailure = useCallback((error: unknown) => {
    if (isUnauthorized(error)) {
      setAccessRequired(true);
      setOperatorSession(null);
      setMessage("Operator session required");
    }
  }, []);

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
        .catch((error) => {
          markAccessFailure(error);
          setPlatform((current) => failedResource(current, error, "Platform status unavailable"));
        }),
      apiJson<OperationsDashboard>("/api/dashboard/operations", { cache: "no-store" })
        .then((data) => setOperations(readyResource(data)))
        .catch((error) => {
          markAccessFailure(error);
          setOperations((current) => failedResource(current, error, "Operations dashboard unavailable"));
        }),
      apiJson<OcrPipelineProfile>("/api/ocr/pipeline", { cache: "no-store" })
        .then((data) => setOcrPipeline(readyResource(data)))
        .catch((error) => {
          markAccessFailure(error);
          setOcrPipeline((current) => failedResource(current, error, "OCR pipeline unavailable"));
        }),
      apiJson<TemplateStudio>("/api/admin/templates/studio", { cache: "no-store" })
        .then((data) => setTemplateStudio(readyResource(data)))
        .catch((error) => {
          markAccessFailure(error);
          setTemplateStudio((current) => failedResource(current, error, "Template library unavailable"));
        }),
      apiJson<IntegrationProfilesResponse>("/api/integrations/profiles", { cache: "no-store" })
        .then((data) => setProfiles(readyResource(data)))
        .catch((error) => {
          markAccessFailure(error);
          setProfiles((current) => failedResource(current, error, "Integration profiles unavailable"));
        }),
      apiJson<AiHealth>("/api/ai/health", { cache: "no-store" })
        .then((data) => setAiHealth(readyResource(data)))
        .catch((error) => setAiHealth((current) => failedResource(current, error, "AI health unavailable"))),
      apiJson<IntegrationOperations>("/api/integrations/operations", { cache: "no-store" })
        .then((data) => setIntegrationOps(readyResource(data)))
        .catch((error) => {
          markAccessFailure(error);
          setIntegrationOps((current) => failedResource(current, error, "Integration operations unavailable"));
        }),
      apiJson<VerificationAdaptersResponse>("/api/verification/adapters", { cache: "no-store" })
        .then((data) => setVerificationAdapters(readyResource(data)))
        .catch((error) => {
          markAccessFailure(error);
          setVerificationAdapters((current) => failedResource(current, error, "Verification adapters unavailable"));
        }),
      apiJson<AccuracyAnalytics>("/api/analytics/accuracy", { cache: "no-store" })
        .then((data) => setAccuracy(readyResource(data)))
        .catch((error) => {
          markAccessFailure(error);
          setAccuracy((current) => failedResource(current, error, "Accuracy analytics unavailable"));
        }),
    ]);
  }, [markAccessFailure]);

  const loadCases = useCallback(async () => {
    setMessage("Refreshing");
    try {
      const data = await apiJson<KycCase[]>("/api/cases", { cache: "no-store" });
      setCases(data);
      setSelectedId((current) => current ?? data[0]?.id ?? null);
      setMessage("Connected");
    } catch (error) {
      handleApiFailure(error, "Backend unavailable");
    }
  }, [handleApiFailure]);

  const loadStandaloneDocuments = useCallback(async () => {
    try {
      const data = await apiJson<DocumentRecord[]>("/api/documents", { cache: "no-store" });
      setStandaloneDocuments(data);
      setSelectedStandaloneDocumentId((current) => current ?? data[0]?.id ?? null);
    } catch (error) {
      handleApiFailure(error, "Standalone documents unavailable");
    }
  }, [handleApiFailure]);

  const loadJobs = useCallback(async () => {
    setJobQueue((current) => loadingResource(current));
    try {
      const data = await listJobs();
      setJobQueue(readyResource(data));
    } catch (error) {
      setJobQueue((current) => failedResource(current, error, "Job queue unavailable"));
    }
  }, []);

  const loadPublicContext = useCallback(async () => {
    setAiHealth((current) => loadingResource(current));
    try {
      const data = await apiJson<AiHealth>("/api/ai/health", { cache: "no-store" });
      setAiHealth(readyResource(data));
    } catch (error) {
      setAiHealth((current) => failedResource(current, error, "AI health unavailable"));
    }
  }, []);

  const refreshAll = useCallback(async () => {
    setAccessRequired(false);
    await Promise.all([loadCases(), loadStandaloneDocuments(), loadJobs(), loadEnterpriseContext()]);
  }, [loadCases, loadJobs, loadStandaloneDocuments, loadEnterpriseContext]);

  const handleOperatorSignIn = useCallback(
    async (payload: OperatorSessionRequest) => {
      setBusy(true);
      try {
        const session = await createOperatorSession(payload);
        setOperatorSession(session.principal);
        setAccessRequired(false);
        setMessage("Operator session active");
        await refreshAll();
      } catch (error) {
        handleApiFailure(error, "Unable to create operator session");
      } finally {
        setBusy(false);
      }
    },
    [handleApiFailure, refreshAll],
  );

  const handleOperatorSignOut = useCallback(async () => {
    await logoutOperatorSession().catch(() => undefined);
    setOperatorSession(null);
    setAccessRequired(true);
    setMessage("Operator session required");
    await loadPublicContext();
  }, [loadPublicContext]);

  useEffect(() => {
    let active = true;
    void loadOperatorSession()
      .then(async (session) => {
        if (!active) {
          return;
        }
        setOperatorSession(session.principal);
        setAccessRequired(false);
        setMessage("Operator session active");
        await refreshAll();
      })
      .catch(async () => {
        if (!active) {
          return;
        }
        setOperatorSession(null);
        setAccessRequired(true);
        setMessage("Operator session required");
        await loadPublicContext();
      });
    return () => {
      active = false;
    };
  }, [loadPublicContext, refreshAll]);

  const loadCaseIntelligence = useCallback(async (caseId: string) => {
    setIntelligence((current) => loadingResource(current));
    try {
      const data = await apiJson<CaseIntelligence>(`/api/cases/${caseId}/intelligence`, { cache: "no-store" });
      setIntelligence(readyResource(data));
    } catch (error) {
      setIntelligence((current) => failedResource(current, error, "Application guidance unavailable"));
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
    if (!selectedCase) {
      setSelectedDocumentId(null);
      return;
    }
    if (selectedCase.documents.some((document) => document.id === selectedDocumentId)) {
      return;
    }
    setSelectedDocumentId(selectedCase.documents[0]?.id ?? null);
  }, [selectedCase, selectedDocumentId]);

  useEffect(() => {
    if (standaloneDocuments.some((document) => document.id === selectedStandaloneDocumentId)) {
      return;
    }
    setSelectedStandaloneDocumentId(standaloneDocuments[0]?.id ?? null);
  }, [selectedStandaloneDocumentId, standaloneDocuments]);

  useEffect(() => {
    setFieldDrafts(Object.fromEntries(JSON.parse(fieldDraftSeed) as [string, string][]));
  }, [fieldDraftSeed]);

  useEffect(() => {
    if (!exportProfiles.includes(profileKey)) {
      setProfileKey(exportProfiles[0] ?? "cbs_standard");
    }
  }, [exportProfiles, profileKey]);

  async function createCase(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setBusy(true);
    setMessage("Creating application");
    try {
      const created = await apiJson<KycCase>("/api/cases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_type: caseType,
          applicant_name: applicantName,
          customer_ref: customerRef,
          institution_id: "client-financial-institution",
          branch_code: "primary-branch",
        }),
      });
      mergeCase(created);
      setMessage("Application created");
      void loadEnterpriseContext();
      return created;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Application creation failed");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function uploadDocument(targetCase: KycCase, uploadFile: File, statusLabel = "Processing document") {
    setBusy(true);
    setMessage(statusLabel);
    setExportJson("");
    try {
      const form = new FormData();
      form.append("declared_document_type", "unknown");
      form.append("file", uploadFile);
      const result = await apiJson<KycCase | JobEnvelope>(`/api/cases/${targetCase.id}/documents`, {
        method: "POST",
        body: form,
      });
      if (isJobEnvelope(result)) {
        setMessage(`Document queued · ${compactId(result.job_id)}`);
        void loadJobs();
        return targetCase;
      }
      const updated = result;
      const previousDocumentIds = new Set(targetCase.documents.map((document) => document.id));
      const uploadedDocument =
        updated.documents.find((document) => !previousDocumentIds.has(document.id)) ??
        updated.documents[updated.documents.length - 1] ??
        null;
      mergeCase(updated);
      setSelectedDocumentId(uploadedDocument?.id ?? null);
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
    if (!selectedFiles.length || !selectedCase) {
      return;
    }
    let currentCase = selectedCase;
    for (const [index, uploadFile] of selectedFiles.entries()) {
      const updated = await uploadDocument(
        currentCase,
        uploadFile,
        selectedFiles.length > 1 ? `Processing ${index + 1} of ${selectedFiles.length}` : "Processing document",
      );
      if (!updated) {
        return;
      }
      currentCase = updated;
    }
    setSelectedFiles([]);
  }

  async function uploadStandaloneDocument(uploadFile: File, statusLabel = "Processing standalone document") {
    setBusy(true);
    setMessage(statusLabel);
    setExportJson("");
    try {
      const form = new FormData();
      form.append("declared_document_type", "unknown");
      form.append("file", uploadFile);
      const result = await apiJson<DocumentRecord | JobEnvelope>("/api/documents/upload", {
        method: "POST",
        body: form,
      });
      if (isJobEnvelope(result)) {
        setMessage(`Standalone document queued · ${compactId(result.job_id)}`);
        void loadJobs();
        return result;
      }
      const document = result;
      setStandaloneDocuments((current) => [document, ...current.filter((item) => item.id !== document.id)]);
      setSelectedStandaloneDocumentId(document.id);
      setDocumentLane("standalone");
      setMessage("Standalone document processed");
      void loadEnterpriseContext();
      return document;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Standalone document processing failed");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function handleStandaloneUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!standaloneFiles.length) {
      return;
    }
    for (const [index, uploadFile] of standaloneFiles.entries()) {
      const uploaded = await uploadStandaloneDocument(
        uploadFile,
        standaloneFiles.length > 1
          ? `Processing standalone ${index + 1} of ${standaloneFiles.length}`
          : "Processing standalone document",
      );
      if (!uploaded) {
        return;
      }
    }
    setStandaloneFiles([]);
  }

  async function retryProcessingJob(job: ProcessingJob) {
    setActiveAction(`retry-job-${job.id}`);
    setMessage("Requeueing document job");
    try {
      await retryJob(job.id);
      await loadJobs();
      setMessage("Document job requeued");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not retry job");
    } finally {
      setActiveAction(null);
    }
  }

  async function uploadTemplateDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!templateFiles.length) {
      setMessage("Choose template pages first");
      return;
    }
    setBusy(true);
    setActiveAction("template-upload");
    setMessage("Processing template pages");
    try {
      const form = new FormData();
      form.append("name", templateName || "Untitled Template");
      form.append("document_type", templateDocumentType);
      templateFiles.forEach((file) => form.append("files", file));
      const data = await apiJson<{ draft: TemplateDraft }>("/api/admin/templates/drafts", {
        method: "POST",
        body: form,
      });
      setTemplateDraft(data.draft);
      setSelectedTemplatePageNumber(data.draft.pages[0]?.page_number ?? 1);
      setSelectedTemplateFieldId(data.draft.fields[0]?.id ?? null);
      setTemplateName(data.draft.name);
      setTemplateDocumentType(data.draft.document_type);
      setMessage("Template draft ready");
      void loadEnterpriseContext();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Template processing failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  function updateTemplateField(fieldId: string, patch: Partial<TemplateProfileField>) {
    setTemplateDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        fields: current.fields.map((field) => (field.id === fieldId ? { ...field, ...patch } : field)),
      };
    });
  }

  function updateTemplateFieldBbox(fieldId: string, index: number, value: string) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return;
    }
    setTemplateDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        fields: current.fields.map((field) => {
          if (field.id !== fieldId) {
            return field;
          }
          const bbox = [...field.bbox];
          bbox[index] = numeric;
          return { ...field, bbox };
        }),
      };
    });
  }

  function startTemplateFieldDrag(
    event: ReactPointerEvent<HTMLElement>,
    field: TemplateProfileField,
    mode: TemplateDragMode,
  ) {
    if (!selectedTemplatePage || !templateCanvasRef.current) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    setSelectedTemplateFieldId(field.id);
    setTemplateDrag({
      fieldId: field.id,
      mode,
      startBbox: [...field.bbox],
      startClientX: event.clientX,
      startClientY: event.clientY,
    });
  }

  function addTemplateField() {
    if (!templateDraft || !selectedTemplatePage) {
      return;
    }
    const nextField: TemplateProfileField = {
      id: `tplfld_${Date.now()}`,
      key: "new_field",
      label: "New Field",
      page_number: selectedTemplatePage.page_number,
      bbox: [80, 120, Math.min(520, selectedTemplatePage.width - 80), 168],
      type: "text",
      required: false,
      language_hint: "mixed",
      validation_rule: null,
      extraction_hint: "Reviewer mapped field",
      confidence: 1,
    };
    setTemplateDraft({ ...templateDraft, fields: [...templateDraft.fields, nextField] });
    setSelectedTemplateFieldId(nextField.id);
  }

  function deleteTemplateField(fieldId: string) {
    if (!templateDraft) {
      return;
    }
    const remaining = templateDraft.fields.filter((field) => field.id !== fieldId);
    setTemplateDraft({ ...templateDraft, fields: remaining });
    setSelectedTemplateFieldId(remaining[0]?.id ?? null);
  }

  async function saveTemplateDraft() {
    if (!templateDraft) {
      return null;
    }
    setBusy(true);
    setActiveAction("template-save");
    setMessage("Saving template draft");
    try {
      const data = await apiJson<{ draft: TemplateDraft }>(`/api/admin/templates/drafts/${templateDraft.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: templateName || templateDraft.name,
          document_type: templateDocumentType,
          fields: templateDraft.fields,
        }),
      });
      setTemplateDraft(data.draft);
      setMessage("Template draft saved");
      return data.draft;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Template draft save failed");
      return null;
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function publishTemplateDraft() {
    if (!templateDraft) {
      return;
    }
    const saved = await saveTemplateDraft();
    if (!saved) {
      return;
    }
    setBusy(true);
    setActiveAction("template-publish");
    setMessage("Publishing template");
    setTemplateStudio((current) => loadingResource(current));
    try {
      const data = await apiJson<{ profile: unknown; studio: TemplateStudio }>(
        `/api/admin/templates/drafts/${saved.id}/publish`,
        { method: "POST", headers: { "Content-Type": "application/json" } },
      );
      setTemplateStudio(readyResource(data.studio));
      setTemplateDraft({ ...saved, status: "published" });
      setMessage("Template published");
      void loadEnterpriseContext();
    } catch (error) {
      setTemplateStudio((current) => failedResource(current, error, "Template publish failed"));
      setMessage(error instanceof Error ? error.message : "Template publish failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function handleSearchAddressEvidence(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setBusy(true);
    setActiveAction("address-search");
    setMessage("Searching address dataset");
    try {
      const data = await searchAddressEvidence(addressQuery, { ...addressFilters, limit: 50 });
      setAddressResults(data.results);
      setMessage(`${data.results.length} address matches`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Address search failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  function addressDraftPayload(): Partial<AddressEvidenceRecord> {
    return {
      ...addressDraft,
      aliases_en: addressDraft.aliases_en
        .split("|")
        .map((item) => item.trim())
        .filter(Boolean),
      aliases_np: addressDraft.aliases_np
        .split("|")
        .map((item) => item.trim())
        .filter(Boolean),
      visibility: "tenant_private",
      source: "reviewer_approved",
    };
  }

  function resetAddressDraft() {
    setAddressEditingId(null);
    setAddressDraft((current) => ({ ...current, name_en: "", name_np: "", aliases_en: "", aliases_np: "" }));
  }

  function startEditingAddressEvidence(record: AddressEvidenceRecord) {
    setAddressEditingId(record.id);
    setAddressDraft({
      district_name: record.district_name ?? "",
      local_level_name: record.local_level_name ?? "",
      ward: record.ward ?? "",
      kind: record.kind || "area_or_tole",
      name_en: record.name_en ?? "",
      name_np: record.name_np ?? "",
      aliases_en: (record.aliases_en ?? []).join(" | "),
      aliases_np: (record.aliases_np ?? []).join(" | "),
    });
  }

  function parseAddressImportRecords(): Partial<AddressEvidenceRecord>[] {
    const parsed = JSON.parse(addressImportDraft);
    if (Array.isArray(parsed)) return parsed;
    if (parsed && typeof parsed === "object") {
      const objectPayload = parsed as { records?: unknown };
      if (Array.isArray(objectPayload.records)) return objectPayload.records as Partial<AddressEvidenceRecord>[];
      return [parsed as Partial<AddressEvidenceRecord>];
    }
    return [];
  }

  async function handleCreateAddressEvidence(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setBusy(true);
    setActiveAction(addressEditingId ? "address-update" : "address-create");
    setMessage(addressEditingId ? "Updating address record" : "Adding address record");
    try {
      const data = addressEditingId
        ? await updateAddressEvidence(addressEditingId, addressDraftPayload())
        : await createAddressEvidence(addressDraftPayload());
      setAddressResults((current) => {
        const remaining = current.filter((record) => record.id !== data.record.id);
        return [data.record, ...remaining];
      });
      resetAddressDraft();
      setMessage(addressEditingId ? "Address record updated" : "Address record added");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Address save failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function handleDeleteAddressEvidence(record: AddressEvidenceRecord) {
    if (record.visibility === "shared_reference") {
      setMessage("Shared reference records are system-managed");
      return;
    }
    const confirmed = window.confirm(`Delete ${record.name_en || record.name_np || record.id}?`);
    if (!confirmed) return;
    setBusy(true);
    setActiveAction(`address-delete-${record.id}`);
    setMessage("Deleting address record");
    try {
      await deleteAddressEvidence(record.id);
      setAddressResults((current) => current.filter((item) => item.id !== record.id));
      if (addressEditingId === record.id) resetAddressDraft();
      setMessage("Address record deleted");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Address delete failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function handleImportAddressEvidence(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setBusy(true);
    setActiveAction("address-import");
    setMessage("Importing address records");
    try {
      const records = parseAddressImportRecords();
      if (!records.length) throw new Error("Paste a JSON object, JSON array, or { records: [...] } payload");
      const data = await importAddressEvidence(records);
      setAddressResults((current) => {
        const importedIds = new Set(data.records.map((record) => record.id));
        return [...data.records, ...current.filter((record) => !importedIds.has(record.id))];
      });
      setAddressImportDraft("");
      setMessage(`${data.count} address records imported`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Address import failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function runSamplePacket() {
    let target: KycCase | null = selectedCase;
    if (!target) {
      target = await createCase();
    }
    if (!target) {
      return;
    }
    const samples: { name: string; text: string }[] = [
      {
        name: "np-citizenship.txt",
        text: "Government of Nepal\nName: Sita Sharma\nCitizenship No: 27-01-78-12345\nDistrict: Kathmandu\nPhoto attached\nSignature present",
      },
      {
        name: "account-opening-form.txt",
        text: "Account Opening Form\nCustomer Name: Sita Sharma\nMobile: 9841000000\nAddress: Kathmandu\nAccount Type: Savings\nCustomer Declaration Signed",
      },
      {
        name: "pan-certificate.txt",
        text: "Permanent Account Number\nName: Sita Sharma\nPAN: 123456789",
      },
      {
        name: "asba-application.txt",
        text: "NMB Bank Limited\nहितोपत्र खरिद सार्वजनिक निष्कासन दरखास्त फारम\nDP ID: 13013700\nClient ID: 00151978\nApplicant Name: Sita Sharma\nBank Account No: 007004469105\nApplied Units: 400\nAmount: 40000",
      },
    ];
    let currentCase = target;
    for (const sample of samples) {
      const fileBlob = new File([sample.text], sample.name, { type: "text/plain" });
      const updated = await uploadDocument(currentCase, fileBlob);
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

  async function submitCaseReview(decision: "save" | "approve" | "reject") {
    if (!selectedCase) {
      return;
    }
    const fieldUpdates = { ...pendingFieldUpdates };
    if (decision === "save" && Object.keys(fieldUpdates).length === 0) {
      setMessage("No corrections to save");
      return;
    }
    setBusy(true);
    setActiveAction(decision === "approve" ? "approve" : "save-corrections");
    setMessage(decision === "approve" ? "Approving" : "Saving corrections");
    try {
      const updated = await apiJson<KycCase>(`/api/cases/${selectedCase.id}/review`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reviewer: operatorActor,
          decision,
          document_id: selectedDocument?.id,
          field_updates: fieldUpdates,
          note:
            decision === "approve"
              ? "Maker-checker review complete."
              : `${Object.keys(fieldUpdates).length} extracted field correction(s) saved.`,
        }),
      });
      mergeCase(updated);
      setMessage(decision === "approve" ? "Approved" : "Corrections saved");
      void loadEnterpriseContext();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : decision === "approve" ? "Approval failed" : "Correction save failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function submitStandaloneReview(decision: "save" | "approve" | "reject") {
    if (!selectedStandaloneDocument) {
      return;
    }
    const fieldUpdates = { ...pendingFieldUpdates };
    if (decision === "save" && Object.keys(fieldUpdates).length === 0) {
      setMessage("No corrections to save");
      return;
    }
    setBusy(true);
    setActiveAction(decision === "approve" ? "approve" : "save-corrections");
    setMessage(decision === "approve" ? "Approving document" : "Saving corrections");
    try {
      const updated = await apiJson<DocumentRecord>(`/api/documents/${selectedStandaloneDocument.id}/review`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reviewer: operatorActor,
          decision,
          document_id: selectedStandaloneDocument.id,
          field_updates: fieldUpdates,
          note:
            decision === "approve"
              ? "Standalone document review complete."
              : `${Object.keys(fieldUpdates).length} extracted field correction(s) saved.`,
        }),
      });
      setStandaloneDocuments((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setSelectedStandaloneDocumentId(updated.id);
      setMessage(decision === "approve" ? "Document approved" : "Corrections saved");
      void loadStandaloneDocuments();
      void loadEnterpriseContext();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : decision === "approve" ? "Approval failed" : "Correction save failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function saveFieldCorrections() {
    if (section === "documents" && documentLane === "standalone") {
      await submitStandaloneReview("save");
      return;
    }
    await submitCaseReview("save");
  }

  async function addManualField() {
    if (!selectedDocument) {
      setMessage("Select a document first");
      return;
    }
    const label = manualFieldLabel.trim();
    const key = manualFieldResolvedKey;
    const value = manualFieldValue.trim();
    if (!label || !value) {
      setMessage("Add a field label and value");
      return;
    }
    if (extractedFieldKeys.has(key)) {
      setMessage(`${labelize(key)} already exists. Edit it in the field list.`);
      return;
    }

    setBusy(true);
    setActiveAction("add-manual-field");
    setMessage("Adding field");
    try {
      if (section === "documents" && documentLane === "standalone") {
        const updated = await apiJson<DocumentRecord>(`/api/documents/${selectedDocument.id}/review`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            reviewer: operatorActor,
            decision: "save",
            document_id: selectedDocument.id,
            field_updates: { [key]: value },
            note: `Reviewer mapped missing field: ${label}.`,
          }),
        });
        setStandaloneDocuments((current) => current.map((item) => (item.id === updated.id ? updated : item)));
        setSelectedStandaloneDocumentId(updated.id);
        void loadStandaloneDocuments();
      } else if (selectedCase) {
        const updated = await apiJson<KycCase>(`/api/cases/${selectedCase.id}/review`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            reviewer: operatorActor,
            decision: "save",
            document_id: selectedDocument.id,
            field_updates: { [key]: value },
            note: `Reviewer mapped missing field: ${label}.`,
          }),
        });
        mergeCase(updated);
      }
      setManualFieldLabel("");
      setManualFieldKey("");
      setManualFieldValue("");
      setMessage("Field added");
      void loadEnterpriseContext();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Field add failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function approveCase() {
    if (section === "documents" && documentLane === "standalone") {
      await submitStandaloneReview("approve");
      return;
    }
    await submitCaseReview("approve");
  }

  async function reanalyzeStandaloneDocument() {
    if (!selectedStandaloneDocument) {
      return;
    }
    setBusy(true);
    setActiveAction("reanalyze-document");
    setMessage("Reanalyzing document");
    setExportJson("");
    try {
      const updated = await apiJson<DocumentRecord>(`/api/documents/${selectedStandaloneDocument.id}/reanalyze`, {
        method: "POST",
      });
      setStandaloneDocuments((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setSelectedStandaloneDocumentId(updated.id);
      setMessage("Document reanalyzed");
      void loadEnterpriseContext();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Reanalysis failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function replaceStandaloneDocument(uploadFile: File) {
    if (!selectedStandaloneDocument) {
      return;
    }
    if (
      typeof window !== "undefined" &&
      !window.confirm("Replace this document with the selected file? Existing extracted fields will be regenerated.")
    ) {
      return;
    }
    setBusy(true);
    setActiveAction("replace-document");
    setMessage("Replacing document");
    setExportJson("");
    try {
      const form = new FormData();
      form.append("declared_document_type", "unknown");
      form.append("file", uploadFile);
      const updated = await apiJson<DocumentRecord>(`/api/documents/${selectedStandaloneDocument.id}/replace`, {
        method: "POST",
        body: form,
      });
      setStandaloneDocuments((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setSelectedStandaloneDocumentId(updated.id);
      setMessage("Document replaced");
      void loadEnterpriseContext();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Replace failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function reanalyzeApplicationDocument() {
    if (!selectedCase || !selectedApplicationDocument) {
      return;
    }
    setBusy(true);
    setActiveAction("reanalyze-application-document");
    setMessage("Reanalyzing application document");
    setExportJson("");
    try {
      const updated = await apiJson<KycCase>(
        `/api/cases/${selectedCase.id}/documents/${selectedApplicationDocument.id}/reanalyze`,
        { method: "POST" },
      );
      mergeCase(updated);
      setSelectedDocumentId(selectedApplicationDocument.id);
      setMessage("Application document reanalyzed");
      void loadEnterpriseContext();
      void loadCaseIntelligence(updated.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Application reanalysis failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function replaceApplicationDocument(uploadFile: File) {
    if (!selectedCase || !selectedApplicationDocument) {
      return;
    }
    if (
      typeof window !== "undefined" &&
      !window.confirm("Replace this application document? The old extracted fields will be regenerated from the new file.")
    ) {
      return;
    }
    setBusy(true);
    setActiveAction("replace-application-document");
    setMessage("Replacing application document");
    setExportJson("");
    try {
      const form = new FormData();
      form.append("declared_document_type", selectedApplicationDocument.declared_document_type);
      form.append("file", uploadFile);
      const updated = await apiJson<KycCase>(
        `/api/cases/${selectedCase.id}/documents/${selectedApplicationDocument.id}/replace`,
        {
          method: "POST",
          body: form,
        },
      );
      mergeCase(updated);
      setSelectedDocumentId(selectedApplicationDocument.id);
      setMessage("Application document replaced");
      void loadEnterpriseContext();
      void loadCaseIntelligence(updated.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Application replace failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function archiveStandaloneDocument() {
    if (!selectedStandaloneDocument) {
      return;
    }
    if (
      typeof window !== "undefined" &&
      !window.confirm("Archive this document? It will stay in history but will no longer be active for review.")
    ) {
      return;
    }
    setBusy(true);
    setActiveAction("archive-document");
    setMessage("Archiving document");
    setExportJson("");
    try {
      const updated = await apiJson<DocumentRecord>(`/api/documents/${selectedStandaloneDocument.id}/archive`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: "Archived from document workbench." }),
      });
      setStandaloneDocuments((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setSelectedStandaloneDocumentId(updated.id);
      setMessage("Document archived");
      void loadEnterpriseContext();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Archive failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function linkStandaloneDocument(mode: "copy" | "move") {
    if (!selectedStandaloneDocument || !selectedCase) {
      setMessage("Select a target application");
      return;
    }
    if (
      mode === "move" &&
      typeof window !== "undefined" &&
      !window.confirm("Move this library document to the selected application? The library copy will be archived.")
    ) {
      return;
    }
    setBusy(true);
    setActiveAction(mode === "copy" ? "copy-to-application" : "move-to-application");
    setMessage(mode === "copy" ? "Copying to application" : "Moving to application");
    setExportJson("");
    try {
      const result = await apiJson<{ case: KycCase; document: DocumentRecord; mode: "copy" | "move" }>(
        `/api/documents/${selectedStandaloneDocument.id}/link-application`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ case_id: selectedCase.id, mode }),
        },
      );
      mergeCase(result.case);
      setStandaloneDocuments((current) => current.map((item) => (item.id === result.document.id ? result.document : item)));
      setSelectedStandaloneDocumentId(result.document.id);
      setSelectedDocumentId(result.document.id);
      setMessage(mode === "copy" ? "Copied to application" : "Moved to application");
      void loadEnterpriseContext();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : mode === "copy" ? "Copy failed" : "Move failed");
    } finally {
      setBusy(false);
      setActiveAction(null);
    }
  }

  async function exportSelectedDocument() {
    setBusy(true);
    setActiveAction("export-document");
    setMessage("Preparing export");
    try {
      const data =
        section === "documents" && documentLane === "standalone" && selectedStandaloneDocument
          ? await apiJson<unknown>(`/api/documents/${selectedStandaloneDocument.id}/export`, { cache: "no-store" })
          : selectedCase
            ? await apiJson<unknown>(`/api/cases/${selectedCase.id}/export`, { cache: "no-store" })
            : null;
      if (!data) {
        setMessage("Select a document first");
        return;
      }
      setExportJson(JSON.stringify(data, null, 2));
      setMessage("Export preview ready");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Export failed");
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
        body: JSON.stringify({ reviewer: operatorActor, queue: "high_value_kyc", priority: "high" }),
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
          author: operatorActor,
          message: "Source image and registry result need checker confirmation.",
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
          requester: operatorActor,
          reason: "Source document must be refreshed before final approval.",
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
    if (reviewFieldDraftValue === (reviewField.value ?? "")) {
      setMessage("Edit the selected field before recording a correction");
      return;
    }
    setBusy(true);
    setActiveAction("record-correction");
    setMessage("Recording correction");
    setAccuracy((current) => loadingResource(current));
    try {
      const data = await apiJson<CorrectionResponse>("/api/analytics/corrections", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: selectedCase.id,
          field_key: reviewField.key,
          old_value: reviewField.value,
          new_value: reviewFieldDraftValue,
          corrected_by: operatorActor,
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
    const templateFields = primaryExtractionFields.filter((field) => !field.key.startsWith("ocr_line_"));
    if (!selectedDocument || !templateFields.length) {
      setMessage("Add at least one mapped field before creating a template");
      return;
    }
    setBusy(true);
    setActiveAction("configure-template");
    setMessage("Creating template");
    setTemplateStudio((current) => loadingResource(current));
    try {
      const data = await apiJson<{ studio: TemplateStudio }>("/api/admin/templates/studio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_type: selectedDocument.document_type,
          name: `${labelize(selectedDocument.document_type)} Template`,
          fields: templateFields.map((field, index) => ({
            key: field.key,
            label: field.label,
            required: field.required,
            bbox: field.evidence.bbox ?? [80, 100 + index * 48, 920, 134 + index * 48],
          })),
          validation_rules: templateFields.flatMap((field) => {
            const rules = field.required ? [{ field_key: field.key, rule: "required", severity: "error" }] : [];
            if (/(date|dob)/i.test(field.key)) {
              rules.push({ field_key: field.key, rule: "date", severity: "warning" });
            }
            return rules;
          }),
        }),
      });
      setTemplateStudio(readyResource(data.studio));
      setMessage("Template created from reviewed fields");
    } catch (error) {
      setTemplateStudio((current) => failedResource(current, error, "Template creation failed"));
      setMessage(error instanceof Error ? error.message : "Template creation failed");
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
    setMessage("Configuring core system webhook");
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
      setMessage("Core system webhook configured");
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
          <div className="flex min-w-0 items-start gap-4">
            <LipiOcrLogo className="mt-0.5 shrink-0" size="md" />
            <div className="min-w-0">
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-700">Enterprise workspace</p>
              <h1 className="mt-1 text-3xl font-extrabold text-slate-950">{activeNav.label}</h1>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">{activeNav.description}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Pill icon={<Activity size={16} />} label={message} />
            <Pill icon={<BrainCircuit size={16} />} label={aiHealth.data?.enabled ? "LipiCore active" : "LipiCore standby"} />
            <button
              className="inline-flex h-10 items-center gap-2 rounded-full border border-slate-200 bg-white px-4 font-semibold text-slate-700 shadow-[var(--shadow-soft)] hover:-translate-y-0.5 hover:border-cyan-200 hover:text-cyan-700 hover:shadow-[var(--shadow-lift)]"
              onClick={refreshAll}
              type="button"
            >
              <RefreshCcw size={16} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      {accessRequired || operatorSession ? (
        <LoginPanel
          onSignIn={handleOperatorSignIn}
          onSignOut={handleOperatorSignOut}
          session={operatorSession}
          signingIn={busy}
        />
      ) : null}

      <section className="border-b border-border-soft/80 bg-slate-50/70">
        <div className="mx-auto max-w-[1800px] px-4 pt-4 sm:px-6">
          <ModuleSwitcher activeHref={activeHref} activeSection={section} />
        </div>
        {!isDocumentWorkspace ? (
          <div className="mx-auto grid max-w-[1800px] gap-3 px-4 py-4 sm:px-6 lg:grid-cols-5">
            <Kpi icon={<Boxes size={18} />} label="Applications" value={summaryCounts.total_cases} />
            <Kpi icon={<ClipboardCheck size={18} />} label="Review" value={summaryCounts.review_required} />
            <Kpi icon={<ShieldAlert size={18} />} label="Exceptions" value={summaryCounts.exceptions} />
            <Kpi icon={<BadgeCheck size={18} />} label="Approved" value={summaryCounts.approved} />
            <Kpi icon={<FileText size={18} />} label="Documents" value={summaryCounts.documents} />
          </div>
        ) : null}
      </section>

      {isDocumentWorkspace ? (
        <section className="mx-auto max-w-[1800px] space-y-4 px-4 py-5 sm:px-6">
          <div className="inline-flex max-w-full rounded-full border border-slate-200 bg-white p-1 shadow-[var(--shadow-soft)]">
            {[
              { value: "application", label: "Application Documents", icon: <Boxes size={14} /> },
              { value: "standalone", label: "Document Library", icon: <Database size={14} /> },
            ].map((item) => {
              const active = documentLane === item.value;
              return (
                <button
                  className={`inline-flex h-9 min-w-0 items-center gap-2 rounded-full px-4 text-sm font-bold transition ${
                    active
                      ? "bg-gradient-to-r from-cyan-600 to-teal-500 text-white shadow-[var(--shadow-button)]"
                      : "text-slate-600 hover:bg-cyan-50 hover:text-cyan-700"
                  }`}
                  key={item.value}
                  onClick={() => setDocumentLane(item.value as DocumentLane)}
                  type="button"
                >
                  <span className="shrink-0">{item.icon}</span>
                  <span className="truncate">{item.label}</span>
                </button>
              );
            })}
          </div>

          {documentLane === "application" ? (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
            <section className="min-w-0 rounded-2xl border border-slate-200 bg-white shadow-[var(--shadow-soft)]">
              <div className="border-b border-slate-100 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Applications</p>
                    <h2 className="mt-1 text-lg font-extrabold text-slate-950">
                      {selectedCase?.applicant_name ?? "Select an application"}
                    </h2>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <StatusBadge status={selectedCase?.status} />
                    <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 font-mono font-semibold text-slate-600">
                      {selectedCase?.integration_ref ?? compactId(selectedCase?.id)}
                    </span>
                  </div>
                </div>
                <div className="mt-3">
                  <input
                    className="h-10 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 text-sm font-semibold text-slate-800 outline-none focus:border-cyan-500 focus:bg-white focus:ring-2 focus:ring-cyan-500/20"
                    placeholder="Search applications"
                    value={applicationSearch}
                    onChange={(event) => setApplicationSearch(event.target.value)}
                  />
                </div>
                <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
                  {filteredCases.map((item) => (
                    <button
                      className={`min-w-[210px] rounded-xl border px-3 py-2 text-left transition ${
                        selectedCase?.id === item.id
                          ? "border-cyan-400 bg-cyan-50 text-cyan-950 shadow-[0_12px_30px_-20px_rgba(14,165,168,0.7)]"
                          : "border-slate-200 bg-white text-slate-600 hover:border-cyan-200 hover:bg-cyan-50/60"
                      }`}
                      key={item.id}
                      onClick={() => {
                        setSelectedId(item.id);
                        setExportJson("");
                      }}
                      type="button"
                    >
                      <span className="block truncate text-sm font-bold">{item.applicant_name}</span>
                      <span className="mt-1 flex items-center justify-between gap-2 text-xs">
                        <span className="truncate font-mono">{item.integration_ref ?? compactId(item.id)}</span>
                        <span>{item.documents.length} documents</span>
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-[var(--shadow-soft)]">
              <form className="space-y-3" onSubmit={handleUpload}>
                <div className="flex items-center justify-between gap-3">
                  <SectionLabel icon={<Upload size={15} />} label="Add Document" />
                  <div className="flex items-center gap-2">
                    <span className="inline-flex h-9 items-center gap-1.5 rounded-full border border-cyan-100 bg-cyan-50 px-3 text-xs font-bold text-cyan-700">
                      <SearchCheck size={14} />
                      Auto Detect
                    </span>
                    <ActionButton busy={busy && message.includes("Processing")} icon={<Layers3 size={14} />} onClick={runSamplePacket}>
                      Sample documents
                    </ActionButton>
                  </div>
                </div>
                <label className="flex min-h-20 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-cyan-200 bg-cyan-50/60 px-3 text-center hover:border-cyan-300 hover:bg-cyan-50">
                  <Upload className="mb-2 text-cyan-700" size={20} />
                  <span className="max-w-full truncate text-sm font-semibold">{selectedFileLabel}</span>
                  <input
                    className="sr-only"
                    multiple
                    type="file"
                    onChange={(event) => setSelectedFiles(Array.from(event.target.files ?? []))}
                  />
                </label>
                <ActionButton disabled={busy || !selectedFiles.length || !selectedCase} icon={<Upload size={14} />} type="submit">
                  Upload {selectedFiles.length > 1 ? `(${selectedFiles.length})` : ""}
                </ActionButton>
              </form>
            </section>
          </div>
          ) : (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
            <section className="min-w-0 rounded-2xl border border-slate-200 bg-white shadow-[var(--shadow-soft)]">
              <div className="border-b border-slate-100 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Document Library</p>
                    <h2 className="mt-1 text-lg font-extrabold text-slate-950">
                      {selectedStandaloneDocument?.filename ?? "No standalone document"}
                    </h2>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <StatusBadge status={selectedStandaloneDocument?.status} />
                    <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 font-mono font-semibold text-slate-600">
                      {compactId(selectedStandaloneDocument?.id)}
                    </span>
                  </div>
                </div>
                <div className="mt-3">
                  <input
                    className="h-10 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 text-sm font-semibold text-slate-800 outline-none focus:border-cyan-500 focus:bg-white focus:ring-2 focus:ring-cyan-500/20"
                    placeholder="Search documents"
                    value={documentSearch}
                    onChange={(event) => setDocumentSearch(event.target.value)}
                  />
                </div>
                <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
                  {filteredStandaloneDocuments.length ? (
                    filteredStandaloneDocuments.map((document) => (
                      <button
                        className={`min-w-[230px] rounded-xl border px-3 py-2 text-left transition ${
                          selectedStandaloneDocument?.id === document.id
                            ? "border-cyan-400 bg-cyan-50 text-cyan-950 shadow-[0_12px_30px_-20px_rgba(14,165,168,0.7)]"
                            : "border-slate-200 bg-white text-slate-600 hover:border-cyan-200 hover:bg-cyan-50/60"
                        }`}
                        key={document.id}
                        onClick={() => {
                          setSelectedStandaloneDocumentId(document.id);
                          setExportJson("");
                        }}
                        type="button"
                      >
                        <span className="block truncate text-sm font-bold">{document.filename}</span>
                        <span className="mt-1 flex items-center justify-between gap-2 text-xs">
                          <span className="truncate">{labelize(document.document_type)}</span>
                          <span>{pct(document.overall_confidence)}</span>
                        </span>
                      </button>
                    ))
                  ) : (
                    <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-sm font-medium text-slate-500">
                      {standaloneDocuments.length ? "No documents match this search." : "Upload a document to start the library."}
                    </div>
                  )}
                </div>
                {recentJobs.length ? (
                  <div className="mt-4 rounded-2xl border border-cyan-100 bg-cyan-50/40 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="text-xs font-bold uppercase tracking-[0.14em] text-cyan-700">Processing</p>
                        <p className="mt-1 text-xs text-slate-500">Async OCR and LipiCore jobs.</p>
                      </div>
                      <button
                        className="rounded-lg border border-cyan-200 bg-white px-3 py-1.5 text-xs font-bold text-cyan-700 transition hover:border-cyan-300 hover:bg-cyan-50"
                        onClick={() => void loadJobs()}
                        type="button"
                      >
                        Refresh
                      </button>
                    </div>
                    <div className="mt-3 grid gap-2">
                      {recentJobs.map((job) => (
                        <div
                          className="flex items-center justify-between gap-3 rounded-xl border border-white/80 bg-white px-3 py-2 text-xs shadow-[0_8px_24px_-20px_rgba(14,165,168,0.65)]"
                          key={job.id}
                        >
                          <div className="min-w-0">
                            <p className="truncate font-bold text-slate-900">
                              {labelize(job.job_type)} · {compactId(job.id)}
                            </p>
                            <p className="mt-0.5 truncate text-slate-500">
                              {job.error?.message ?? (job.result ? "Ready for review" : String(job.payload.filename ?? job.target_id))}
                            </p>
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            <StatusBadge status={job.status} />
                            {job.status === "failed" ? (
                              <button
                                className="rounded-lg border border-rose-200 bg-white px-2.5 py-1 font-bold text-rose-700 transition hover:bg-rose-50"
                                disabled={activeAction === `retry-job-${job.id}`}
                                onClick={() => void retryProcessingJob(job)}
                                type="button"
                              >
                                Retry
                              </button>
                            ) : null}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
                {cases.length ? (
                  <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">
                          Target Application
                        </p>
                        <p className="mt-1 text-xs text-slate-500">Copy or move sends this document here.</p>
                      </div>
                      {selectedCase ? <StatusBadge status={selectedCase.status} /> : null}
                    </div>
                    <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
                      {filteredCases.map((item) => {
                        const active = selectedCase?.id === item.id;
                        return (
                          <button
                            className={`min-w-[190px] rounded-xl border px-3 py-2 text-left text-xs transition ${
                              active
                                ? "border-cyan-400 bg-white text-cyan-950 shadow-[0_10px_25px_-18px_rgba(14,165,168,0.7)]"
                                : "border-slate-200 bg-white/70 text-slate-600 hover:border-cyan-200 hover:bg-white"
                            }`}
                            key={item.id}
                            onClick={() => setSelectedId(item.id)}
                            type="button"
                          >
                            <span className="block truncate font-bold">{item.applicant_name}</span>
                            <span className="mt-1 flex items-center justify-between gap-2">
                              <span className="truncate font-mono">{item.integration_ref ?? compactId(item.id)}</span>
                              <span>{item.documents.length} docs</span>
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-[var(--shadow-soft)]">
              <form className="space-y-3" onSubmit={handleStandaloneUpload}>
                <div className="flex items-center justify-between gap-3">
                  <SectionLabel icon={<Upload size={15} />} label="Upload to Library" />
                  <span className="inline-flex h-9 items-center gap-1.5 rounded-full border border-cyan-100 bg-cyan-50 px-3 text-xs font-bold text-cyan-700">
                    <SearchCheck size={14} />
                    Auto Detect
                  </span>
                </div>
                <label className="flex min-h-20 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-cyan-200 bg-cyan-50/60 px-3 text-center hover:border-cyan-300 hover:bg-cyan-50">
                  <Upload className="mb-2 text-cyan-700" size={20} />
                  <span className="max-w-full truncate text-sm font-semibold">{standaloneFileLabel}</span>
                  <input
                    className="sr-only"
                    multiple
                    type="file"
                    onChange={(event) => setStandaloneFiles(Array.from(event.target.files ?? []))}
                  />
                </label>
                <ActionButton disabled={busy || !standaloneFiles.length} icon={<Upload size={14} />} type="submit">
                  Upload {standaloneFiles.length > 1 ? `(${standaloneFiles.length})` : ""}
                </ActionButton>
              </form>
            </section>
          </div>
          )}

          <div className="grid min-w-0 gap-4 sm:grid-cols-[minmax(0,0.95fr)_minmax(300px,1.05fr)] xl:grid-cols-[minmax(0,1.08fr)_minmax(440px,0.92fr)]">
            <section className="min-w-0 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[var(--shadow-soft)]">
              <div className="border-b border-slate-100 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">
                      {selectedDocument ? labelize(selectedDocument.document_type) : "Document"}
                    </p>
                    <h2 className="mt-1 truncate text-lg font-extrabold text-slate-950">
                      {selectedDocument?.filename ?? "No document selected"}
                    </h2>
                  </div>
                  <div
                    aria-label="Preview overlay mode"
                    className="inline-flex max-w-full rounded-full border border-slate-200 bg-slate-50 p-1"
                    role="radiogroup"
                  >
                    {previewOverlayModes.map((item) => {
                      const active = item.value === previewOverlayMode;
                      return (
                        <button
                          aria-checked={active}
                          className={`inline-flex h-8 min-w-0 items-center gap-1.5 rounded-full px-2.5 text-xs font-bold transition ${
                            active
                              ? "bg-gradient-to-r from-cyan-600 to-teal-500 text-white shadow-[var(--shadow-button)]"
                              : "text-slate-600 hover:bg-white hover:text-cyan-700"
                          }`}
                          key={item.value}
                          onClick={() => setPreviewOverlayMode(item.value)}
                          role="radio"
                          type="button"
                        >
                          <span className="shrink-0">{item.icon}</span>
                          <span className="truncate">{item.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
                {selectedCase && selectedCase.documents.length > 1 ? (
                  <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
                    {selectedCase.documents.map((document) => {
                      const isActive = document.id === selectedDocument?.id;
                      return (
                        <button
                          className={`min-w-[190px] rounded-xl border px-3 py-2 text-left text-xs transition ${
                            isActive
                              ? "border-cyan-500 bg-cyan-50 text-cyan-950"
                              : "border-slate-200 bg-slate-50 text-slate-600 hover:border-cyan-200 hover:bg-white"
                          }`}
                          key={document.id}
                          onClick={() => setSelectedDocumentId(document.id)}
                          type="button"
                        >
                          <span className="block truncate font-bold">{labelize(document.document_type)}</span>
                          <span className="mt-1 block truncate">{document.filename}</span>
                        </button>
                      );
                    })}
	                  </div>
	                ) : null}
	                {documentLane === "standalone" && selectedStandaloneDocument ? (
	                  <div className="mt-3 rounded-2xl border border-cyan-100 bg-cyan-50/50 p-3">
	                    <div className="flex flex-wrap items-start justify-between gap-3">
	                      <div className="min-w-0">
	                        <p className="text-xs font-bold uppercase tracking-[0.14em] text-cyan-700">
	                          LipiCore Understanding
	                        </p>
	                        <p className="mt-1 text-sm font-extrabold text-slate-950">
	                          {labelize(selectedStandaloneDocument.document_type)}
	                        </p>
	                        <p className="mt-1 truncate text-xs text-slate-600">
	                          {selectedStandaloneDocument.summary || "Standalone document processed for review and export."}
	                        </p>
	                      </div>
	                      <span className="rounded-full bg-white px-2.5 py-1 font-mono text-xs font-bold text-cyan-700">
	                        {pct(selectedStandaloneDocument.overall_confidence)}
	                      </span>
	                    </div>
	                  </div>
	                ) : null}
	              </div>

              <div
                className={`relative mx-auto max-h-[calc(100vh-260px)] w-full overflow-hidden bg-white ${
                  selectedImageSrc ? "min-h-[520px]" : "min-h-[360px]"
                }`}
                style={selectedImageSrc ? { aspectRatio: pageAspectRatio(selectedPage) } : undefined}
              >
                {selectedImageSrc ? (
                  // Next/Image is not useful here because the preview source is served by the private OCR API.
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    alt={`${selectedDocument?.filename ?? "Uploaded document"} preview`}
                    className="absolute inset-0 h-full w-full object-contain"
                    src={selectedImageSrc}
                  />
                ) : null}
                {selectedPage && !selectedImageSrc ? (
                  <div className="absolute inset-0 overflow-auto bg-slate-50 p-4">
                    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
                        <div>
                          <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Readable Text</p>
                          <p className="mt-1 text-sm font-semibold text-slate-950">
                            {selectedPage.blocks.length} line{selectedPage.blocks.length === 1 ? "" : "s"} detected
                          </p>
                        </div>
                        <StatusBadge status={selectedDocument?.status} />
                      </div>
                      <div className="mt-3 space-y-2">
                        {selectedPage.blocks.length ? (
                          selectedPage.blocks.map((block, index) => (
                            <div
                              className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-800"
                              key={`${block.text}-${index}`}
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="font-medium">{block.text}</span>
                                <span className="rounded-full bg-white px-2 py-0.5 font-mono text-[11px] font-bold text-slate-500">
                                  {pct(block.confidence)}
                                </span>
                              </div>
                            </div>
                          ))
                        ) : (
                          <p className="text-sm text-slate-500">No readable text was returned for this document.</p>
                        )}
                      </div>
                    </div>
                  </div>
                ) : null}
                <div className="pointer-events-none absolute inset-0 bg-white/10" />
                {selectedImageSrc && selectedPage && previewOverlayMode === "evidence"
                  ? selectedPageEvidenceFields.map((field, index) => {
                      const bbox = field.evidence.bbox;
                      if (!hasUsableBbox(bbox)) {
                        return null;
                      }
                      return (
                        <div
                          className={`absolute rounded-[3px] border transition ${evidenceOverlayTone(field)}`}
                          key={`${field.key}-${index}`}
                          style={bboxStyle(bbox, selectedPage)}
                          title={`${field.label}: ${field.value || "Unclear"} (${pct(field.confidence)})`}
                        />
                      );
                    })
                  : null}
                {selectedImageSrc && selectedPage && previewOverlayMode === "blocks"
                  ? selectedPage.blocks.filter((block) => hasUsableBbox(block.bbox)).map((block, index) => (
                      <div
                        className={`absolute rounded-[3px] border ${
                          block.block_type === "handwriting"
                            ? "border-amber-500/60 bg-amber-300/5"
                            : "border-cyan-500/50 bg-cyan-300/5"
                        }`}
                        key={`${block.text}-${index}`}
                        style={blockStyle(block, selectedPage)}
                        title={`${block.text} (${pct(block.confidence)})`}
                      />
                    ))
                  : null}
                {!selectedPage ? (
                  <div className="absolute inset-0 flex items-center justify-center p-8 text-center text-sm font-medium text-slate-500">
                    Upload or select a document to review.
                  </div>
                ) : null}
              </div>
            </section>

            <section className="min-w-0 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[var(--shadow-soft)]">
              <div className="border-b border-slate-100 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Extracted Data</p>
                    <h2 className="mt-1 text-lg font-extrabold text-slate-950">Review and correct</h2>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {documentLane === "standalone" ? (
                      <>
                        <ActionButton
                          busy={activeAction === "copy-to-application"}
                          disabled={busy || !selectedStandaloneDocument || !selectedCase}
                          icon={<Link2 size={14} />}
                          onClick={() => linkStandaloneDocument("copy")}
                        >
                          Copy to Application
                        </ActionButton>
                        <ActionButton
                          busy={activeAction === "move-to-application"}
                          disabled={busy || !selectedStandaloneDocument || !selectedCase}
                          icon={<Route size={14} />}
                          onClick={() => linkStandaloneDocument("move")}
                        >
                          Move to Application
                        </ActionButton>
                        <ActionButton
                          busy={activeAction === "reanalyze-document"}
                          disabled={busy || !selectedStandaloneDocument}
                          icon={<RefreshCcw size={14} />}
                          onClick={reanalyzeStandaloneDocument}
                        >
                          Reanalyze
                        </ActionButton>
                        <label
                          className={`inline-flex h-10 min-w-0 items-center justify-center gap-2 rounded-full border border-slate-200 bg-white px-3 text-xs font-bold text-slate-700 hover:-translate-y-0.5 hover:border-cyan-200 hover:bg-slate-50 hover:text-cyan-700 hover:shadow-[var(--shadow-soft)] ${
                            busy || !selectedStandaloneDocument ? "cursor-not-allowed opacity-60" : "cursor-pointer"
                          }`}
                        >
                          {activeAction === "replace-document" ? (
                            <Loader2 className="shrink-0 animate-spin" size={14} />
                          ) : (
                            <Upload className="shrink-0" size={14} />
                          )}
                          <span className="truncate">Replace</span>
                          <input
                            className="sr-only"
                            disabled={busy || !selectedStandaloneDocument}
                            type="file"
                            onChange={(event) => {
                              const file = event.target.files?.[0];
                              event.currentTarget.value = "";
                              if (file) {
                                void replaceStandaloneDocument(file);
                              }
                            }}
                          />
                        </label>
                        <ActionButton
                          busy={activeAction === "archive-document"}
                          disabled={busy || !selectedStandaloneDocument}
                          icon={<Archive size={14} />}
                          onClick={archiveStandaloneDocument}
                        >
                          Archive
                        </ActionButton>
                      </>
                    ) : (
                      <>
                        <ActionButton
                          busy={activeAction === "reanalyze-application-document"}
                          disabled={busy || !selectedCase || !selectedApplicationDocument}
                          icon={<RefreshCcw size={14} />}
                          onClick={reanalyzeApplicationDocument}
                        >
                          Reanalyze
                        </ActionButton>
                        <label
                          className={`inline-flex h-10 min-w-0 items-center justify-center gap-2 rounded-full border border-slate-200 bg-white px-3 text-xs font-bold text-slate-700 hover:-translate-y-0.5 hover:border-cyan-200 hover:bg-slate-50 hover:text-cyan-700 hover:shadow-[var(--shadow-soft)] ${
                            busy || !selectedCase || !selectedApplicationDocument
                              ? "cursor-not-allowed opacity-60"
                              : "cursor-pointer"
                          }`}
                        >
                          {activeAction === "replace-application-document" ? (
                            <Loader2 className="shrink-0 animate-spin" size={14} />
                          ) : (
                            <Upload className="shrink-0" size={14} />
                          )}
                          <span className="truncate">Replace</span>
                          <input
                            className="sr-only"
                            disabled={busy || !selectedCase || !selectedApplicationDocument}
                            type="file"
                            onChange={(event) => {
                              const file = event.target.files?.[0];
                              event.currentTarget.value = "";
                              if (file) {
                                void replaceApplicationDocument(file);
                              }
                            }}
                          />
                        </label>
                      </>
                    )}
                    <ActionButton
                      busy={activeAction === "export-document"}
                      disabled={busy || !selectedDocument}
                      icon={<Download size={14} />}
                      onClick={exportSelectedDocument}
                    >
                      Export
                    </ActionButton>
                    <ActionButton
                      busy={activeAction === "save-corrections"}
                      disabled={busy || !selectedDocument || pendingCorrectionCount === 0}
                      icon={<ClipboardCheck size={14} />}
                      onClick={saveFieldCorrections}
                    >
                      Save {pendingCorrectionCount ? `(${pendingCorrectionCount})` : ""}
                    </ActionButton>
                    <ActionButton
                      busy={activeAction === "approve"}
                      disabled={busy || !selectedDocument}
                      icon={<ShieldCheck size={14} />}
                      onClick={approveCase}
                      tone="primary"
                    >
                      Approve
                    </ActionButton>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2">
                  <InfoBox label="Fields" value={`${editableExtractionFields.length}`} />
                  <InfoBox label="Needs Check" value={`${needsReviewCount}`} />
                  <InfoBox label="OCR Text" value={`${rawOcrFields.length}`} />
                </div>
                <div className={`mt-3 rounded-2xl border p-3 ${exportReadinessTone}`}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-[0.14em] opacity-75">Export Readiness</p>
                      <p className="mt-1 text-sm font-extrabold">{exportReadinessStatus}</p>
                    </div>
                    <div className="flex flex-wrap gap-2 text-xs font-bold">
                      <span className="rounded-full bg-white/75 px-2.5 py-1">{missingFieldCount} missing</span>
                      <span className="rounded-full bg-white/75 px-2.5 py-1">{lowConfidenceCount} low confidence</span>
                      <span className="rounded-full bg-white/75 px-2.5 py-1">{pendingCorrectionCount} unsaved</span>
                    </div>
                  </div>
                </div>
                {documentLane === "standalone" && selectedStandaloneDocument?.version_history?.length ? (
                  <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Version History</p>
                      <span className="rounded-full bg-white px-2 py-1 font-mono text-xs font-bold text-slate-500">
                        v{selectedStandaloneDocument.version_history.length}
                      </span>
                    </div>
                    <div className="mt-3 grid gap-2">
                      {selectedStandaloneDocument.version_history
                        .slice(-4)
                        .reverse()
                        .map((version) => (
                          <div
                            className="grid grid-cols-[auto_1fr_auto] items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs"
                            key={`${version.version}-${version.action}-${version.created_at}`}
                          >
                            <span className="rounded-full bg-cyan-50 px-2 py-1 font-mono font-bold text-cyan-700">
                              v{version.version}
                            </span>
                            <span className="min-w-0">
                              <span className="block truncate font-bold text-slate-900">{labelize(version.action)}</span>
                              <span className="mt-0.5 block truncate text-slate-500">{version.filename}</span>
                            </span>
                            <span className="font-mono text-slate-500">{formatDate(version.created_at)}</span>
                          </div>
                        ))}
                    </div>
                  </div>
                ) : null}
                {selectedDocumentIntelligence ? (
                  <div className="mt-3 rounded-2xl border border-cyan-100 bg-cyan-50/50 p-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs font-bold uppercase tracking-[0.14em] text-cyan-700">
                          LipiCore Understanding
                        </p>
                        <p className="mt-1 text-sm font-extrabold text-slate-950">
                          {labelize(selectedDocumentIntelligence.document_type)}
                        </p>
                        <p className="mt-1 truncate text-xs text-slate-600">{selectedDocumentIntelligence.reason}</p>
                      </div>
                      <span className="rounded-full bg-white px-2.5 py-1 font-mono text-xs font-bold text-cyan-700">
                        {pct(selectedDocumentIntelligence.confidence)}
                      </span>
                    </div>
                    <div className="mt-3 grid gap-2 sm:grid-cols-5">
                      <div className="rounded-xl border border-white/80 bg-white px-3 py-2 text-xs">
                        <p className="font-semibold text-slate-500">Variant</p>
                        <p className="mt-1 truncate font-extrabold text-slate-950">
                          {selectedDocumentVariant ? labelize(selectedDocumentVariant.version_family) : "Unclassified"}
                        </p>
                      </div>
                      <div className="rounded-xl border border-white/80 bg-white px-3 py-2 text-xs">
                        <p className="font-semibold text-slate-500">Sides</p>
                        <p className="mt-1 font-mono font-extrabold text-slate-950">{selectedDocumentSections.length}</p>
                      </div>
                      <div className="rounded-xl border border-white/80 bg-white px-3 py-2 text-xs">
                        <p className="font-semibold text-slate-500">Ledger</p>
                        <p className="mt-1 font-mono font-extrabold text-slate-950">{selectedEvidenceLedger.length}</p>
                      </div>
                      <div className="rounded-xl border border-white/80 bg-white px-3 py-2 text-xs">
                        <p className="font-semibold text-slate-500">Assets</p>
                        <p className="mt-1 font-mono font-extrabold text-slate-950">{selectedDocumentAssets.length}</p>
                      </div>
                      <div className="rounded-xl border border-white/80 bg-white px-3 py-2 text-xs">
                        <p className="font-semibold text-slate-500">Locations</p>
                        <p className="mt-1 font-mono font-extrabold text-slate-950">{selectedLocationResolutions.length}</p>
                      </div>
                    </div>
                    {selectedDocumentVariant ? (
                      <div className="mt-3 rounded-xl border border-white/80 bg-white px-3 py-2 text-xs">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-bold text-slate-950">{selectedDocumentVariant.label}</span>
                          <span className="font-mono font-bold text-cyan-700">{pct(selectedDocumentVariant.confidence)}</span>
                        </div>
                        <p className="mt-1 line-clamp-2 text-slate-500">{selectedDocumentVariant.reason}</p>
                      </div>
                    ) : null}
                    {selectedDocumentSections.length ? (
                      <div className="mt-3 rounded-xl border border-white/80 bg-white p-3 text-xs">
                        <p className="font-bold uppercase tracking-[0.12em] text-slate-500">Document Sides</p>
                        <div className="mt-2 grid gap-2 sm:grid-cols-2">
                          {selectedDocumentSections.map((section) => (
                            <div className="rounded-lg bg-slate-50 px-3 py-2" key={section.id}>
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="font-bold text-slate-900">{section.label || labelize(section.side)}</span>
                                <span className="font-mono font-bold text-cyan-700">{pct(section.confidence)}</span>
                              </div>
                              <p className="mt-1 truncate text-slate-500">
                                Page {section.page_number} · {labelize(section.side)}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {canonicalFieldRows.length ? (
                      <div className="mt-3 grid gap-2 sm:grid-cols-2">
                        {canonicalFieldRows.map(([key, value]) => (
                          <div className="min-w-0 rounded-xl border border-white/80 bg-white px-3 py-2 text-xs" key={key}>
                            <p className="truncate font-semibold text-slate-500">{labelize(key)}</p>
                            <p className="mt-1 truncate font-bold text-slate-950">{value}</p>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {selectedDocumentAssets.length ? (
                      <div className="mt-3 rounded-xl border border-white/80 bg-white p-3 text-xs">
                        <p className="font-bold uppercase tracking-[0.12em] text-slate-500">Evidence Assets</p>
                        <div className="mt-2 grid gap-2 sm:grid-cols-2">
                          {selectedDocumentAssets.slice(0, 6).map((asset) => (
                            <div
                              className="flex items-center justify-between gap-3 rounded-lg bg-cyan-50 px-3 py-2"
                              key={`${asset.id}-${asset.asset_type}`}
                            >
                              <span className="inline-flex min-w-0 items-center gap-2">
                                <Fingerprint size={14} className="shrink-0 text-cyan-700" />
                                <span className="truncate font-bold text-slate-900">{labelize(asset.asset_type)}</span>
                              </span>
                              <span className="shrink-0 font-mono font-bold text-cyan-700">{pct(asset.confidence)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {selectedEntityRecords.length ? (
                      <div className="mt-3 rounded-xl border border-white/80 bg-white p-3 text-xs">
                        <p className="font-bold uppercase tracking-[0.12em] text-slate-500">Bilingual Entity Records</p>
                        <div className="mt-2 grid gap-2">
                          {selectedEntityRecords.slice(0, 4).map((record) => (
                            <div className="rounded-lg bg-slate-50 px-3 py-2" key={record.entity_key}>
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="font-bold text-slate-900">{labelize(record.entity_key)}</span>
                                <span className="inline-flex items-center gap-1 rounded-full bg-white px-2 py-0.5 font-semibold text-slate-600">
                                  <StatusDot status={record.status} />
                                  {labelize(record.status)}
                                </span>
                              </div>
                              {record.original_ne || record.original_en ? (
                                <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
                                  <p className="truncate text-slate-600">
                                    <span className="font-semibold text-slate-500">Nepali:</span>{" "}
                                    {record.original_ne || "Not found"}
                                  </p>
                                  <p className="truncate text-slate-600">
                                    <span className="font-semibold text-slate-500">English:</span>{" "}
                                    {record.original_en || "Not found"}
                                  </p>
                                </div>
                              ) : (
                                <p className="mt-1 truncate text-slate-600">{record.value}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {selectedLocationResolutions.length ? (
                      <div className="mt-3 rounded-xl border border-white/80 bg-white p-3 text-xs">
                        <p className="font-bold uppercase tracking-[0.12em] text-slate-500">Nepal Location Registry</p>
                        <div className="mt-2 grid gap-2">
                          {selectedLocationResolutions.slice(0, 4).map((resolution) => (
                            <div
                              className="rounded-lg bg-slate-50 px-3 py-2"
                              key={`${resolution.field_prefix}-${resolution.source_value}-${resolution.local_level_code ?? resolution.district_code}`}
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="inline-flex min-w-0 items-center gap-2 font-bold text-slate-900">
                                  <MapPin size={14} className="shrink-0 text-cyan-700" />
                                  <span className="truncate">{labelize(resolution.field_prefix ?? "address")}</span>
                                </span>
                                <span className="inline-flex items-center gap-1 rounded-full bg-white px-2 py-0.5 font-semibold text-slate-600">
                                  <StatusDot status={resolution.status} />
                                  {labelize(resolution.status)}
                                </span>
                              </div>
                              <p className="mt-2 truncate font-semibold text-slate-800">
                                {[resolution.local_level_key, resolution.district_name, resolution.province_name]
                                  .filter(Boolean)
                                  .join(", ") || "Location unresolved"}
                                {resolution.ward ? ` · Ward ${resolution.ward}` : ""}
                              </p>
                              {resolution.warnings.length ? (
                                <p className="mt-1 line-clamp-2 text-amber-700">{resolution.warnings.map(labelize).join(", ")}</p>
                              ) : (
                                <p className="mt-1 line-clamp-2 text-slate-500">
                                  Registry matched and filled structured province, district, local level, and ward fields.
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {selectedEvidenceLedger.length ? (
                      <div className="mt-3 rounded-xl border border-white/80 bg-white p-3 text-xs">
                        <p className="font-bold uppercase tracking-[0.12em] text-slate-500">Evidence Ledger Sample</p>
                        <div className="mt-2 grid gap-2">
                          {selectedEvidenceLedger.slice(0, 5).map((entry) => (
                            <div
                              className="grid grid-cols-[auto_1fr_auto] items-center gap-2 rounded-lg bg-slate-50 px-3 py-2"
                              key={entry.entry_id}
                            >
                              <span className="font-mono font-bold text-slate-500">p{entry.page_number}</span>
                              <span className="min-w-0 truncate font-semibold text-slate-800">{entry.text}</span>
                              <span className="rounded-full bg-white px-2 py-0.5 font-mono font-bold text-slate-500">
                                {entry.mapped_field_key ? labelize(entry.mapped_field_key) : labelize(entry.block_type)}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {semanticChecks.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {semanticChecks.slice(0, 3).map((check) => (
                          <span
                            className="inline-flex max-w-full items-center gap-2 rounded-full border border-white bg-white px-2.5 py-1 text-xs font-semibold text-slate-700"
                            key={check.key}
                            title={check.message}
                          >
                            <StatusDot status={check.status} />
                            <span className="truncate">{labelize(check.key)}</span>
                          </span>
                        ))}
                      </div>
                    ) : null}
                    {languagePairs.length ? (
                      <div className="mt-3 grid gap-2 sm:grid-cols-2">
                        {languagePairs.slice(0, 6).map((pair) => (
                          <div
                            className="min-w-0 rounded-xl border border-white/80 bg-white px-3 py-2 text-xs"
                            key={`${pair.canonical_key}-${pair.nepali_value}-${pair.english_value}`}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <p className="truncate font-bold text-slate-950">{labelize(pair.canonical_key)}</p>
                              <span className="inline-flex items-center gap-1 rounded-full bg-slate-50 px-2 py-0.5 font-semibold text-slate-600">
                                <StatusDot status={pair.status} />
                                {labelize(pair.status)}
                              </span>
                            </div>
                            <div className="mt-2 grid gap-1.5">
                              <p className="truncate text-slate-600">
                                <span className="font-semibold text-slate-500">Nepali:</span> {pair.nepali_value || "Not found"}
                              </p>
                              <p className="truncate text-slate-600">
                                <span className="font-semibold text-slate-500">English:</span> {pair.english_value || "Not found"}
                              </p>
                            </div>
                            {pair.message ? <p className="mt-2 line-clamp-2 text-slate-500">{pair.message}</p> : null}
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {confidenceRepairs.length ? (
                      <div className="mt-3 rounded-xl border border-white/80 bg-white p-3 text-xs">
                        <p className="font-bold uppercase tracking-[0.12em] text-slate-500">Confidence Repair</p>
                        <div className="mt-2 grid gap-2">
                          {confidenceRepairs.slice(0, 3).map((repair) => (
                            <div className="rounded-lg bg-cyan-50 px-3 py-2" key={`${repair.target_field}-${repair.source_field_used}`}>
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="font-bold text-slate-900">{labelize(repair.target_field)}</span>
                                <span className="font-mono font-bold text-cyan-700">
                                  {pct(repair.original_confidence)} to {pct(repair.confidence)}
                                </span>
                              </div>
                              <p className="mt-1 text-slate-600">
                                Source: {labelize(repair.source_field_used)} · Suggested: {repair.corrected_value}
                              </p>
                              <p className="mt-1 line-clamp-2 text-slate-500">{repair.audit_reason}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {entityReconciliations.length ? (
                      <div className="mt-3 rounded-xl border border-white/80 bg-white p-3 text-xs">
                        <p className="font-bold uppercase tracking-[0.12em] text-slate-500">Entity Reconciliation</p>
                        <div className="mt-2 grid gap-2">
                          {entityReconciliations.slice(0, 3).map((item) => (
                            <div className="rounded-lg bg-emerald-50 px-3 py-2" key={`${item.left_filename}-${item.right_filename}`}>
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="font-bold text-slate-900">{labelize(item.status)}</span>
                                <span className="font-mono font-bold text-emerald-700">{pct(item.confidence)}</span>
                              </div>
                              <p className="mt-1 text-slate-600">
                                {item.left_value} matches {item.right_value}
                              </p>
                              <p className="mt-1 line-clamp-2 text-slate-500">{item.reason}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>

              <div className="max-h-[calc(100vh-260px)] min-h-[520px] overflow-auto p-4">
                <div className="mb-4 rounded-2xl border border-cyan-100 bg-white p-3 shadow-[0_4px_20px_-12px_rgba(14,165,168,0.35)]">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <SectionLabel icon={<Plus size={15} />} label="Add Missing Field" />
                      <p className="mt-1 truncate text-xs text-slate-500">
                        Map a field LipiCore missed, then create the template from reviewed fields.
                      </p>
                    </div>
                    <span className="rounded-full bg-cyan-50 px-2 py-1 font-mono text-xs font-bold text-cyan-700">
                      {manualFieldResolvedKey}
                    </span>
                  </div>
                  <div className="mt-3 grid gap-2 md:grid-cols-[1fr_0.8fr]">
                    <label className="block text-xs font-bold text-slate-600">
                      Field label
                      <input
                        className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm font-semibold text-slate-950 outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                        onChange={(event) => setManualFieldLabel(event.target.value)}
                        placeholder="Applicant Name, BOID, जन्म मिति"
                        value={manualFieldLabel}
                      />
                    </label>
                    <label className="block text-xs font-bold text-slate-600">
                      Export key
                      <input
                        className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 font-mono text-sm text-slate-950 outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                        onChange={(event) => setManualFieldKey(fieldKeyFromLabel(event.target.value))}
                        placeholder={manualFieldResolvedKey}
                        value={manualFieldKey}
                      />
                    </label>
                  </div>
                  <label className="mt-2 block text-xs font-bold text-slate-600">
                    Value
                    <textarea
                      className="mt-1 min-h-12 w-full resize-y rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold leading-6 text-slate-950 outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                      onChange={(event) => setManualFieldValue(event.target.value)}
                      placeholder="Value exactly as confirmed by reviewer"
                      rows={2}
                      value={manualFieldValue}
                    />
                  </label>
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs text-slate-500">This field is saved with audit evidence and included in template creation.</p>
                    <ActionButton
                      busy={activeAction === "add-manual-field"}
                      disabled={busy || !selectedDocument || !manualFieldLabel.trim() || !manualFieldValue.trim()}
                      icon={<Plus size={14} />}
                      onClick={addManualField}
                    >
                      Add Field
                    </ActionButton>
                  </div>
                </div>
                {editableExtractionFields.length ? (
                  <div className="space-y-4">
                    {groupedEditableFields.map((group) => (
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3" key={group.key}>
                        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                          <div className="min-w-0">
                            <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">{group.label}</p>
                            <p className="mt-1 truncate text-xs text-slate-500">{group.description}</p>
                          </div>
                          <span className="rounded-full bg-white px-2 py-1 font-mono text-xs font-bold text-slate-500">
                            {group.fields.length}
                          </span>
                        </div>
                        <div className="space-y-3">
                          {group.fields.map((field) => {
                            const draftKey = fieldEditorKey(field);
                            const draftValue = fieldDrafts[draftKey] ?? field.value ?? "";
                            const changed = draftValue !== (field.value ?? "");
                            const suggestedValue = field.corrected_value?.trim();
                            const candidateOptions = field.correction_candidates ?? [];
                            const isAddressCandidate = candidateOptions.some((candidate) =>
                              (candidate.sources || []).some((source) =>
                                [
                                  "nepal_location_registry",
                                  "address_evidence_store",
                                  "fuzzy_alias_match",
                                  "reviewer_approved",
                                ].includes(source),
                              ),
                            );
                            const hasCorrectionSuggestion = Boolean(suggestedValue && suggestedValue !== field.value);
                            return (
                              <label
                                className={`block rounded-xl border p-3 transition ${
                                  changed ? "border-cyan-300 bg-cyan-50/60" : "border-slate-200 bg-white"
                                }`}
                                key={draftKey}
                              >
                                <span className="flex items-start justify-between gap-3">
                                  <span className="min-w-0">
                                    <span className="block truncate text-sm font-bold text-slate-950">{field.label}</span>
                                    <span className="mt-1 block truncate text-xs text-slate-500">
                                      {field.validation_message}
                                    </span>
                                  </span>
                                  <span className="shrink-0 rounded-full border border-slate-200 bg-slate-50 px-2 py-1 font-mono text-xs font-bold text-slate-600">
                                    {pct(field.confidence)}
                                  </span>
                                </span>
                                <textarea
                                  className="mt-3 min-h-12 w-full resize-y rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold leading-6 text-slate-950 outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                                  onChange={(event) =>
                                    setFieldDrafts((current) => ({
                                      ...current,
                                      [draftKey]: event.target.value,
                                    }))
                                  }
                                  rows={draftValue.length > 80 ? 3 : 2}
                                  value={draftValue}
                                />
                                {candidateOptions.length ? (
                                  <span className="mt-3 block rounded-lg border border-cyan-100 bg-cyan-50 px-3 py-2 text-xs">
                                    <span className="flex flex-wrap items-center justify-between gap-2">
                                      <span className="font-bold text-cyan-950">
                                        {isAddressCandidate ? "Possible address matches" : "Possible name matches"}
                                      </span>
                                      <span className="text-slate-500">Original: {field.original_ocr_value || field.value}</span>
                                    </span>
                                    <span className="mt-2 grid gap-2">
                                      {candidateOptions.slice(0, 5).map((candidate) => (
                                        <button
                                          className="flex min-h-10 items-center justify-between gap-3 rounded-lg border border-white bg-white px-3 py-2 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-soft)]"
                                          key={`${draftKey}-${candidate.suggested_value}-${candidate.confidence}`}
                                          onClick={(event) => {
                                            event.preventDefault();
                                            setFieldDrafts((current) => ({
                                              ...current,
                                              [draftKey]: candidate.suggested_value,
                                            }));
                                          }}
                                          type="button"
                                        >
                                          <span className="min-w-0">
                                            <span className="block truncate font-extrabold text-slate-950">
                                              {candidate.suggested_value}
                                            </span>
                                            <span className="mt-0.5 block truncate text-slate-500">
                                              {(candidate.sources ?? []).map(labelize).join(" + ") || "Name lexicon"}
                                            </span>
                                            {isAddressCandidate && "score_breakdown" in candidate && candidate.score_breakdown ? (
                                              <span className="text-[11px] font-semibold text-slate-500">
                                                {Object.entries(candidate.score_breakdown)
                                                  .filter(([, score]) => Number(score) > 0)
                                                  .map(([key]) => labelize(key))
                                                  .slice(0, 4)
                                                  .join(" + ")}
                                              </span>
                                            ) : null}
                                          </span>
                                          <span className="shrink-0 rounded-full bg-cyan-50 px-2 py-1 font-mono font-bold text-cyan-700">
                                            {pct(candidate.confidence)}
                                          </span>
                                        </button>
                                      ))}
                                    </span>
                                    {candidateOptions[0]?.audit_reason ? (
                                      <span className="mt-2 block line-clamp-2 text-slate-500">
                                        {candidateOptions[0].audit_reason}
                                      </span>
                                    ) : null}
                                  </span>
                                ) : hasCorrectionSuggestion ? (
                                  <span className="mt-3 block rounded-lg border border-cyan-100 bg-cyan-50 px-3 py-2 text-xs">
                                    <span className="flex flex-wrap items-center justify-between gap-2">
                                      <span className="font-bold text-cyan-950">
                                        LipiCore bilingual suggestion
                                      </span>
                                      <span className="font-mono font-bold text-cyan-700">
                                        {pct(field.correction_confidence ?? field.confidence)}
                                      </span>
                                    </span>
                                    <span className="mt-1 block text-slate-700">
                                      Original: <span className="font-semibold">{field.original_ocr_value || field.value}</span>
                                    </span>
                                    <span className="mt-1 block text-slate-700">
                                      Suggested from {labelize(field.source_field_used || "paired field")}:{" "}
                                      <span className="font-semibold">{suggestedValue}</span>
                                    </span>
                                    {field.audit_reason ? (
                                      <span className="mt-1 block line-clamp-2 text-slate-500">{field.audit_reason}</span>
                                    ) : null}
                                    <button
                                      className="mt-2 inline-flex h-8 items-center rounded-full bg-white px-3 text-xs font-bold text-cyan-700 shadow-sm transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-soft)]"
                                      onClick={(event) => {
                                        event.preventDefault();
                                        setFieldDrafts((current) => ({
                                          ...current,
                                          [draftKey]: suggestedValue ?? "",
                                        }));
                                      }}
                                      type="button"
                                    >
                                      Use suggestion
                                    </button>
                                  </span>
                                ) : null}
                                <span className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs">
                                  <span className="truncate text-slate-500">
                                    p{field.evidence.source_page} · {field.evidence.evidence_text || "No source text"}
                                  </span>
                                  <span className="font-semibold text-cyan-700">{extractionSourceLabel(field)}</span>
                                </span>
                              </label>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
                    No extracted fields available for this document.
                  </div>
                )}
                {exportJson ? (
                  <div className="mt-4 rounded-xl border border-slate-200 bg-slate-950 p-3 text-xs text-slate-100">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <span className="font-bold uppercase tracking-[0.14em] text-cyan-200">Export Preview</span>
                      <button
                        className="rounded-full border border-white/10 px-2 py-1 font-semibold text-slate-300 hover:bg-white/10"
                        onClick={() => setExportJson("")}
                        type="button"
                      >
                        Clear
                      </button>
                    </div>
                    <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words font-mono leading-5">
                      {exportJson}
                    </pre>
                  </div>
                ) : null}
              </div>
            </section>
          </div>
        </section>
      ) : (
      <div className={workspaceGridClass}>
        {showLeftRail ? (
        <aside className="min-w-0 space-y-4">
          {section === "cases" ? (
          <Panel title="Intake" icon={<Upload size={16} />}>
            <form className="space-y-3" onSubmit={createCase}>
              <FieldLabel label="Application Type">
                <SegmentedPicker
                  ariaLabel="Application type"
                  options={caseTypes}
                  value={caseType}
                  onChange={(next) => setCaseType(next as CaseType)}
                />
              </FieldLabel>
              <FieldLabel label="Applicant">
                <input
                  className="h-10 w-full rounded-xl border border-slate-200 px-3 text-sm outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                  value={applicantName}
                  onChange={(event) => setApplicantName(event.target.value)}
                />
              </FieldLabel>
              <FieldLabel label="Customer / Application ID">
                <input
                  className="h-10 w-full rounded-xl border border-slate-200 px-3 font-mono text-sm outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                  value={customerRef}
                  onChange={(event) => setCustomerRef(event.target.value)}
                />
              </FieldLabel>
              <button
                className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-full bg-gradient-to-r from-cyan-600 to-teal-500 px-3 text-sm font-bold text-white shadow-[var(--shadow-button)] hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)] disabled:opacity-60"
                disabled={busy}
                type="submit"
              >
                {busy && activeAction === null ? <Loader2 className="animate-spin" size={16} /> : <Plus size={16} />}
                Create Application
              </button>
            </form>
          </Panel>
          ) : null}

          <Panel title="Work Queue" icon={<Workflow size={16} />}>
            <div className="space-y-3">
              <div className="grid gap-2">
                {(operations.data?.lanes ?? []).map((lane) => (
                  <button
                    className="grid grid-cols-[1fr_auto] gap-2 rounded-xl border border-slate-200 bg-white p-3 text-left shadow-sm hover:-translate-y-0.5 hover:border-cyan-200 hover:shadow-[var(--shadow-soft)]"
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
                      className={`mb-2 block w-full rounded-xl border p-3 text-left shadow-sm hover:-translate-y-0.5 hover:border-cyan-200 hover:shadow-[var(--shadow-soft)] ${
                        selectedCase?.id === item.id ? "border-cyan-300 bg-cyan-50 text-cyan-950" : "border-slate-200 bg-white"
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
                        <span>{item.documents.length} documents</span>
                      </span>
                    </button>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">No active applications</p>
                )}
              </div>
            </div>
          </Panel>
        </aside>
        ) : null}

        <section className="min-w-0 space-y-4">
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

          {section === "admin" ? (
          <Panel title="Address Dataset" icon={<MapPin size={16} />}>
            <div className="grid gap-4 xl:grid-cols-[minmax(0,0.88fr)_minmax(360px,0.72fr)]">
              <div className="min-w-0 space-y-3">
                <form className="rounded-xl border border-slate-200 bg-slate-50 p-3" onSubmit={handleSearchAddressEvidence}>
                  <div className="grid gap-2 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1fr)_96px_auto]">
                    <input
                      className="h-10 min-w-0 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-800 outline-none focus:border-cyan-500 focus:bg-white focus:ring-2 focus:ring-cyan-500/20"
                      placeholder="Search address names or aliases"
                      value={addressQuery}
                      onChange={(event) => setAddressQuery(event.target.value)}
                    />
                    <input
                      className="h-10 min-w-0 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                      placeholder="District"
                      value={addressFilters.district}
                      onChange={(event) => setAddressFilters((current) => ({ ...current, district: event.target.value }))}
                    />
                    <input
                      className="h-10 min-w-0 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                      placeholder="Municipality / VDC"
                      value={addressFilters.localLevel}
                      onChange={(event) => setAddressFilters((current) => ({ ...current, localLevel: event.target.value }))}
                    />
                    <input
                      className="h-10 min-w-0 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                      placeholder="Ward"
                      value={addressFilters.ward}
                      onChange={(event) => setAddressFilters((current) => ({ ...current, ward: event.target.value }))}
                    />
                    <ActionButton busy={activeAction === "address-search"} disabled={busy} icon={<SearchCheck size={14} />} type="submit">
                      Search
                    </ActionButton>
                  </div>
                </form>
                <div className="max-h-[360px] overflow-auto rounded-xl border border-slate-200">
                  {addressResults.length ? (
                    addressResults.map((record) => (
                      <div
                        className="grid gap-2 border-b border-slate-100 p-3 text-xs last:border-b-0 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_112px_92px]"
                        key={record.id}
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-bold text-slate-950">{record.name_en || record.name_np || "Unnamed"}</p>
                          <p className="mt-1 truncate text-slate-500">
                            {[labelize(record.kind), record.name_np].filter(Boolean).join(" · ")}
                          </p>
                        </div>
                        <div className="min-w-0">
                          <p className="truncate font-semibold text-slate-700">
                            {[record.district_name, record.local_level_name].filter(Boolean).join(" / ") || "Unscoped"}
                          </p>
                          <p className="mt-1 truncate text-slate-500">
                            {[record.ward ? `Ward ${record.ward}` : "", ...(record.aliases_en ?? [])].filter(Boolean).join(" · ") ||
                              "No aliases"}
                          </p>
                        </div>
                        <div className="min-w-0 text-right md:text-left">
                          <StatusBadge status={record.visibility ?? "tenant_private"} />
                          <p className="mt-1 truncate font-mono text-[11px] text-slate-500">{record.source ?? "manual_seed"}</p>
                        </div>
                        <div className="flex items-center gap-1 lg:justify-end">
                          <IconButton
                            ariaLabel="Edit address evidence"
                            disabled={busy || record.visibility === "shared_reference"}
                            icon={<Pencil size={14} />}
                            onClick={() => startEditingAddressEvidence(record)}
                          />
                          <IconButton
                            ariaLabel="Delete address evidence"
                            disabled={busy || record.visibility === "shared_reference"}
                            icon={<Trash2 size={14} />}
                            onClick={() => void handleDeleteAddressEvidence(record)}
                          />
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="p-4 text-sm text-slate-500">No address records loaded</p>
                  )}
                </div>
              </div>
              <form className="min-w-0 space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-3" onSubmit={handleCreateAddressEvidence}>
                <SectionLabel icon={<Plus size={15} />} label="Add area, tole, or street" />
                <div className="grid gap-2 sm:grid-cols-2">
                  <FieldLabel label="Name">
                    <input
                      className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                      placeholder="Samakhusi"
                      value={addressDraft.name_en}
                      onChange={(event) => setAddressDraft((current) => ({ ...current, name_en: event.target.value }))}
                    />
                  </FieldLabel>
                  <FieldLabel label="Aliases">
                    <input
                      className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                      placeholder="Samakushi | Samakhushi"
                      value={addressDraft.aliases_en}
                      onChange={(event) => setAddressDraft((current) => ({ ...current, aliases_en: event.target.value }))}
                    />
                  </FieldLabel>
                  <FieldLabel label="Nepali Name">
                    <input
                      className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                      placeholder="सामाखुसी"
                      value={addressDraft.name_np}
                      onChange={(event) => setAddressDraft((current) => ({ ...current, name_np: event.target.value }))}
                    />
                  </FieldLabel>
                  <FieldLabel label="Nepali Aliases">
                    <input
                      className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                      placeholder="सामाखुशी | सामाखुसी चोक"
                      value={addressDraft.aliases_np}
                      onChange={(event) => setAddressDraft((current) => ({ ...current, aliases_np: event.target.value }))}
                    />
                  </FieldLabel>
                  <FieldLabel label="District">
                    <input
                      className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                      value={addressDraft.district_name}
                      onChange={(event) => setAddressDraft((current) => ({ ...current, district_name: event.target.value }))}
                    />
                  </FieldLabel>
                  <FieldLabel label="Local Level">
                    <input
                      className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                      value={addressDraft.local_level_name}
                      onChange={(event) => setAddressDraft((current) => ({ ...current, local_level_name: event.target.value }))}
                    />
                  </FieldLabel>
                  <FieldLabel label="Ward">
                    <input
                      className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                      value={addressDraft.ward}
                      onChange={(event) => setAddressDraft((current) => ({ ...current, ward: event.target.value }))}
                    />
                  </FieldLabel>
                  <FieldLabel label="Kind">
                    <SegmentedPicker
                      ariaLabel="Address evidence kind"
                      compact
                      options={[
                        { value: "area_or_tole", label: "Area" },
                        { value: "street_or_road", label: "Street" },
                      ]}
                      value={addressDraft.kind}
                      onChange={(kind) => setAddressDraft((current) => ({ ...current, kind }))}
                    />
                  </FieldLabel>
                </div>
                <ActionButton
                  busy={activeAction === "address-create" || activeAction === "address-update"}
                  className="w-full"
                  disabled={busy || (!addressDraft.name_en.trim() && !addressDraft.name_np.trim())}
                  icon={<Plus size={14} />}
                  type="submit"
                  tone="primary"
                >
                  {addressEditingId ? "Update Record" : "Add Record"}
                </ActionButton>
                {addressEditingId ? (
                  <ActionButton className="w-full" disabled={busy} icon={<RefreshCcw size={14} />} onClick={resetAddressDraft} type="button">
                    Cancel Edit
                  </ActionButton>
                ) : null}
                <div className="space-y-2 border-t border-slate-200 pt-3">
                  <SectionLabel icon={<Upload size={15} />} label="Import JSON records" />
                  <textarea
                    className="min-h-28 w-full resize-y rounded-xl border border-slate-200 bg-white px-3 py-2 font-mono text-xs text-slate-800 outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                    placeholder='[{"kind":"street_or_road","district_name":"Kathmandu","local_level_name":"Kathmandu Metropolitan City","ward":"26","name_en":"Example Road","aliases_en":["Example Rd"]}]'
                    value={addressImportDraft}
                    onChange={(event) => setAddressImportDraft(event.target.value)}
                  />
                  <ActionButton
                    busy={activeAction === "address-import"}
                    className="w-full"
                    disabled={busy || !addressImportDraft.trim()}
                    icon={<Upload size={14} />}
                    onClick={() => void handleImportAddressEvidence()}
                    type="button"
                  >
                    Import Records
                  </ActionButton>
                </div>
              </form>
            </div>
          </Panel>
          ) : null}

          {["cases", "documents", "review", "verification"].includes(section) ? (
          <Panel title={selectedCase?.applicant_name ?? "Application Workbench"} icon={<Eye size={16} />}>
            {selectedCase ? (
              <div className="grid min-w-0 gap-4 2xl:grid-cols-[minmax(0,0.95fr)_minmax(420px,1.05fr)]">
                <div className="min-w-0 space-y-3">
                  <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                    <Info label="File" value={compactId(selectedCase.id)} />
                    <Info label="Type" value={labelize(selectedCase.case_type)} />
                    <Info label="Branch" value={selectedCase.branch_code ?? "primary-branch"} />
                    <Info label="Readiness" value={pct(readinessScore)} />
                  </div>
                  {selectedCase.documents.length > 1 ? (
                    <div className="grid max-h-40 min-w-0 grid-cols-2 gap-2 overflow-y-auto rounded-2xl border border-slate-200 bg-slate-50 p-2 sm:grid-cols-3 2xl:grid-cols-2">
                      {selectedCase.documents.map((document) => {
                        const isActive = document.id === selectedDocument?.id;
                        return (
                          <button
                            className={`min-w-0 rounded-xl border px-3 py-2 text-left text-xs transition ${
                              isActive
                                ? "border-cyan-500 bg-white text-cyan-950 shadow-[0_10px_25px_-16px_rgba(14,165,168,0.55)]"
                                : "border-slate-200 bg-white/70 text-slate-600 hover:border-cyan-200 hover:bg-white"
                            }`}
                            key={document.id}
                            onClick={() => setSelectedDocumentId(document.id)}
                            type="button"
                          >
                            <span className="block truncate font-semibold">{labelize(document.document_type)}</span>
                            <span className="mt-1 block truncate text-[11px] text-slate-500">{document.filename}</span>
                          </button>
                        );
                      })}
                    </div>
                  ) : null}
                  <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-100 shadow-inner">
                    <div className="border-b border-slate-200 bg-white/95 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-xs font-semibold uppercase text-slate-500">
                            {selectedDocument ? labelize(selectedDocument.document_type) : "Document"}
                          </p>
                          <p className="mt-1 truncate text-base font-semibold text-slate-950">
                            {selectedDocument?.filename ?? "No document uploaded"}
                          </p>
                        </div>
                        <div
                          aria-label="Preview overlay mode"
                          className="inline-flex max-w-full rounded-full border border-slate-200 bg-slate-50 p-1"
                          role="radiogroup"
                        >
                          {previewOverlayModes.map((item) => {
                            const active = item.value === previewOverlayMode;
                            return (
                              <button
                                aria-checked={active}
                                className={`inline-flex h-8 min-w-0 items-center gap-1.5 rounded-full px-2.5 text-xs font-bold transition ${
                                  active
                                    ? "bg-gradient-to-r from-cyan-600 to-teal-500 text-white shadow-[var(--shadow-button)]"
                                    : "text-slate-600 hover:bg-white hover:text-cyan-700"
                                }`}
                                key={item.value}
                                onClick={() => setPreviewOverlayMode(item.value)}
                                role="radio"
                                type="button"
                              >
                                <span className="shrink-0">{item.icon}</span>
                                <span className="truncate">{item.label}</span>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                      <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                        <InfoBox label="Text Areas" value={`${selectedPageBlockCount}`} />
                        <InfoBox label="Highlights" value={`${selectedPageEvidenceFields.length}`} />
                        <InfoBox label="Handwriting" value={`${selectedPageHandwritingBlockCount}`} />
                      </div>
                    </div>
                    <div
                      className="relative mx-auto max-h-[720px] min-h-[260px] w-full overflow-hidden bg-white"
                      style={{ aspectRatio: pageAspectRatio(selectedPage) }}
                    >
                      {selectedImageSrc ? (
                        // Next/Image is not useful here because the preview source is served by the private OCR API.
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          alt={`${selectedDocument?.filename ?? "Uploaded document"} preview`}
                          className="absolute inset-0 h-full w-full object-contain"
                          src={selectedImageSrc}
                        />
                      ) : null}
                      <div className="absolute inset-0 bg-white/10" />
                      {selectedPage && previewOverlayMode === "evidence"
                        ? selectedPageEvidenceFields.map((field, index) => {
                            const bbox = field.evidence.bbox;
                            if (!hasUsableBbox(bbox)) {
                              return null;
                            }
                            return (
                              <div
                                className={`absolute rounded-[3px] border transition ${evidenceOverlayTone(field)}`}
                                key={`${field.key}-${index}`}
                                style={bboxStyle(bbox, selectedPage)}
                                title={`${field.label}: ${field.value || "Unclear"} (${pct(field.confidence)})`}
                              />
                            );
                          })
                        : null}
                      {selectedPage && previewOverlayMode === "blocks"
                        ? selectedPage.blocks.filter((block) => hasUsableBbox(block.bbox)).map((block, index) => (
                            <div
                              className={`absolute rounded-[3px] border ${
                                block.block_type === "handwriting"
                                  ? "border-amber-500/60 bg-amber-300/5"
                                  : "border-cyan-500/50 bg-cyan-300/5"
                              }`}
                              key={`${block.text}-${index}`}
                              style={blockStyle(block, selectedPage)}
                              title={`${block.text} (${pct(block.confidence)})`}
                            />
                          ))
                        : null}
                      {!selectedPage ? (
                        <div className="absolute inset-x-6 top-10 text-sm text-slate-500">No source highlights yet.</div>
                      ) : null}
                    </div>
                  </div>
                </div>

                <div className="min-w-0 space-y-3">
                  <div className="rounded-2xl border border-cyan-100 bg-cyan-50/50 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <SectionLabel icon={<FileSearch size={15} />} label="Extraction" />
                      <ActionButton
                        busy={activeAction === "configure-template"}
                        disabled={busy || !selectedDocument || !primaryExtractionFields.length}
                        icon={<FileCog size={14} />}
                        onClick={configureTemplate}
                      >
                        Create Template
                      </ActionButton>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 lg:grid-cols-4">
                      <Info label="Fields" value={`${visibleExtractionFields.length}`} />
                      <Info label="Confidence" value={pct(extractionConfidence)} />
                      <Info label="Template" value={selectedTemplate ? labelize(selectedTemplate.status) : "Not Created"} />
                      <Info label="Coverage" value={pct(templateCoverage)} />
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <ActionButton
                      busy={activeAction === "split"}
                      disabled={busy}
                      icon={<SplitSquareHorizontal size={14} />}
                      onClick={() =>
                        runCaseAction<SplitPreviewResponse>(
                          "split",
                          "Separating documents",
                          `/api/cases/${selectedCase.id}/split-preview`,
                          setSplitPreview,
                        )
                      }
                    >
                      Separate
                    </ActionButton>
                    <ActionButton
                      busy={activeAction === "classify"}
                      disabled={busy}
                      icon={<FileSearch size={14} />}
                      onClick={() =>
                        runCaseAction<ClassificationResponse>(
                          "classify",
                          "Identifying documents",
                          `/api/cases/${selectedCase.id}/classify`,
                          setClassification,
                        )
                      }
                    >
                      Identify
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
                      Check
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
                      <span>Source</span>
                    </div>
                    <div className="max-h-[380px] overflow-auto">
                      {visibleExtractionFields.length ? (
                        visibleExtractionFields.map((field) => (
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
                              <p className="mt-1 truncate text-cyan-700">{extractionSourceLabel(field)}</p>
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
              <div className="p-8 text-sm text-slate-500">Create or select an application.</div>
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

          {section === "templates" ? (
            <TemplateStudioPanel
              activeAction={activeAction}
              addTemplateField={addTemplateField}
              busy={busy}
              deleteTemplateField={deleteTemplateField}
              publishTemplateDraft={publishTemplateDraft}
              saveTemplateDraft={saveTemplateDraft}
              selectedTemplateField={selectedTemplateField}
              selectedTemplatePage={selectedTemplatePage}
              selectedTemplatePageFields={selectedTemplatePageFields}
              setSelectedTemplateFieldId={setSelectedTemplateFieldId}
              setSelectedTemplatePageNumber={setSelectedTemplatePageNumber}
              setTemplateDocumentType={setTemplateDocumentType}
              setTemplateFiles={setTemplateFiles}
              setTemplateName={setTemplateName}
              startTemplateFieldDrag={startTemplateFieldDrag}
              templateCanvasRef={templateCanvasRef}
              templateDocumentType={templateDocumentType}
              templateDraft={templateDraft}
              templateDrag={templateDrag}
              templateFiles={templateFiles}
              templateName={templateName}
              templateStudio={templateStudio}
              updateTemplateField={updateTemplateField}
              updateTemplateFieldBbox={updateTemplateFieldBbox}
              uploadTemplateDraft={uploadTemplateDraft}
            />
          ) : null}

          {["command", "analytics"].includes(section) ? (
          <Panel title="Production Pipeline" icon={<SearchCheck size={16} />}>
            <div className={productionGridClass}>
              {section === "analytics" ? (
                <div className="space-y-3">
                  <SectionLabel icon={<Gauge size={15} />} label="OCR Accuracy Program" />
                  <ResourceError resource={accuracy} />
                  <AccuracyReport accuracy={accuracy.data} />
                </div>
              ) : null}
              {section !== "analytics" ? (
              <div className="space-y-2">
                <SectionLabel icon={<FileSearch size={15} />} label="Recognition: LipiCore" />
                {(ocrPipeline.data?.providers ?? []).map((provider) => (
                  <div className="grid grid-cols-[1fr_auto] gap-3 rounded-xl border border-slate-200 p-3 text-xs" key={provider.key}>
                    <div className="min-w-0">
                      <p className="truncate font-semibold">{providerLabel(provider)}</p>
                      <p className="mt-1 truncate text-slate-500">{providerBestFor(provider)}</p>
                    </div>
                    <StatusBadge status={provider.status} />
                  </div>
                ))}
              </div>
              ) : null}
              {section !== "analytics" ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <SectionLabel icon={<FileCog size={15} />} label="Document Formats" />
                  <ActionButton
                    busy={activeAction === "configure-template"}
                    disabled={busy || !selectedDocument || !primaryExtractionFields.length}
                    icon={<FileCog size={14} />}
                    onClick={configureTemplate}
                  >
                    Create Template
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
        <aside className="min-w-0 space-y-4">
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
                  <p className="mt-1 truncate text-amber-800">{request.fields.join(", ") || "application-level"}</p>
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
                <SegmentedPicker
                  ariaLabel="Export profile"
                  options={exportProfiles.map((key) => ({ value: key, label: labelize(key) }))}
                  value={profileKey}
                  onChange={setProfileKey}
                />
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
      )}
    </main>
  );
}

function Panel({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section className="min-w-0 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[var(--shadow-soft)]">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <h2 className="text-sm font-bold text-slate-950">{title}</h2>
        <span className="rounded-xl bg-cyan-50 p-2 text-cyan-700">{icon}</span>
      </div>
      <div className="min-w-0 p-4">{children}</div>
    </section>
  );
}

function FieldLabel({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="block">
      <span className="mb-2 block text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{label}</span>
      {children}
    </div>
  );
}

function SegmentedPicker({
  ariaLabel,
  compact,
  onChange,
  options,
  value,
}: {
  ariaLabel: string;
  compact?: boolean;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  value: string;
}) {
  return (
    <div
      aria-label={ariaLabel}
      className={`grid gap-2 ${compact ? "grid-cols-2" : "grid-cols-1"}`}
      role="radiogroup"
    >
      {options.map((item) => {
        const active = item.value === value;
        return (
          <button
            aria-checked={active}
            className={`min-h-10 rounded-xl border px-3 py-2 text-left text-xs font-bold ${
              active
                ? "border-cyan-500 bg-gradient-to-r from-cyan-600 to-teal-500 text-white shadow-[var(--shadow-button)]"
                : "border-slate-200 bg-white text-slate-700 hover:-translate-y-0.5 hover:border-cyan-200 hover:bg-cyan-50 hover:text-cyan-700"
            }`}
            key={item.value}
            onClick={() => onChange(item.value)}
            role="radio"
            type="button"
          >
            <span className="block truncate">{item.label}</span>
          </button>
        );
      })}
    </div>
  );
}

function Kpi({ icon, label, value }: { icon: ReactNode; label: string; value: number }) {
  return (
    <div className="group rounded-2xl border border-slate-200 bg-white p-4 shadow-[var(--shadow-soft)] hover:-translate-y-1 hover:shadow-[var(--shadow-lift)]">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-slate-500">{label}</span>
        <span className="rounded-xl bg-cyan-50 p-2 text-cyan-700 group-hover:bg-cyan-100">{icon}</span>
      </div>
      <p className="mt-3 font-mono text-3xl font-bold text-slate-950">{value}</p>
    </div>
  );
}

function Pill({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <span className="inline-flex h-10 max-w-full items-center gap-2 rounded-full border border-slate-200 bg-white px-4 font-semibold text-slate-700 shadow-[var(--shadow-soft)]">
      <span className="shrink-0 text-cyan-700">{icon}</span>
      <span className="truncate">{label}</span>
    </span>
  );
}

function ModuleSwitcher({ activeHref, activeSection }: { activeHref: string; activeSection: WorkspaceSection }) {
  return (
    <nav className="max-w-full rounded-[1.35rem] border border-slate-200 bg-white/95 p-2 shadow-[var(--shadow-soft)]">
      <div className="flex gap-1.5 overflow-x-auto pb-1">
        {workspaceNav.map((item) => {
          const active = item.href === activeHref || item.section === activeSection;
          return (
            <Link
              className={`group inline-flex min-w-fit items-center gap-1.5 rounded-full px-3 py-2.5 text-sm font-bold ${
                active
                  ? "bg-gradient-to-r from-cyan-600 to-teal-500 text-white shadow-[var(--shadow-button)]"
                  : "text-slate-600 hover:-translate-y-0.5 hover:bg-cyan-50 hover:text-cyan-700"
              }`}
              href={item.href}
              key={item.section}
            >
              <span className={active ? "text-white" : "text-slate-400 group-hover:text-cyan-700"}>{item.icon}</span>
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
      <span className="rounded-lg bg-cyan-50 p-1.5 text-cyan-700">{icon}</span>
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

function StatusDot({ status }: { status?: string }) {
  const value = (status ?? "").toLowerCase();
  const color = ["passed", "valid", "approved", "verified"].includes(value)
    ? "bg-emerald-500"
    : ["warning", "needs_review", "review_required"].includes(value)
      ? "bg-amber-500"
      : ["error", "invalid", "rejected", "blocked"].includes(value)
        ? "bg-rose-500"
        : "bg-slate-400";
  return <span className={`h-2 w-2 shrink-0 rounded-full ${color}`} />;
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

function IconButton({
  ariaLabel,
  icon,
  ...props
}: {
  ariaLabel: string;
  icon: ReactNode;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      aria-label={ariaLabel}
      className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 transition hover:-translate-y-0.5 hover:border-cyan-200 hover:text-cyan-700 hover:shadow-[var(--shadow-soft)] disabled:cursor-not-allowed disabled:opacity-50 ${
        props.className ?? ""
      }`}
      title={ariaLabel}
      type={props.type ?? "button"}
    >
      {icon}
    </button>
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
      ? "border-cyan-600 bg-gradient-to-r from-cyan-600 to-teal-500 text-white shadow-[var(--shadow-button)] hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)]"
      : "border-slate-200 bg-white text-slate-700 hover:-translate-y-0.5 hover:border-cyan-200 hover:bg-slate-50 hover:text-cyan-700 hover:shadow-[var(--shadow-soft)]";
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
