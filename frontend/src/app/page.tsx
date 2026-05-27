"use client";

import {
  Activity,
  BadgeCheck,
  Building2,
  ClipboardCheck,
  Download,
  FileSearch,
  FileText,
  History,
  Loader2,
  Network,
  Plus,
  RefreshCcw,
  Save,
  ShieldCheck,
  Upload,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

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

function labelize(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
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

function blockStyle(block: OcrBlock, page: OcrPage) {
  const [x1, y1, x2, y2] = block.bbox;
  return {
    left: `${(x1 / page.width) * 100}%`,
    top: `${(y1 / page.height) * 100}%`,
    width: `${((x2 - x1) / page.width) * 100}%`,
    height: `${((y2 - y1) / page.height) * 100}%`,
  };
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
  const [exportJson, setExportJson] = useState("");

  const selectedCase = useMemo(
    () => cases.find((item) => item.id === selectedId) ?? cases[0] ?? null,
    [cases, selectedId],
  );

  const selectedDocument = selectedCase?.documents[0] ?? null;
  const selectedPage = selectedDocument?.pages[0] ?? null;

  const metrics = useMemo(
    () => ({
      cases: cases.length,
      review: cases.filter((item) => item.status === "review_required").length,
      approved: cases.filter((item) => item.status === "approved").length,
      documents: cases.reduce((total, item) => total + item.documents.length, 0),
    }),
    [cases],
  );

  const refresh = useCallback(async () => {
    setMessage("Syncing");
    try {
      const [caseResponse, aiResponse, manifestResponse] = await Promise.all([
        fetch(`${API_BASE}/api/cases`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/ai/health`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/integrations/manifest`, { cache: "no-store" }),
      ]);
      if (!caseResponse.ok) {
        throw new Error("Case API unavailable");
      }
      const data = (await caseResponse.json()) as KycCase[];
      setCases(data);
      setSelectedId((current) => current ?? data[0]?.id ?? null);
      setAiHealth((await aiResponse.json()) as AiHealth);
      setManifest((await manifestResponse.json()) as IntegrationManifest);
      setMessage("Connected");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Backend unavailable");
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refresh();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

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
    setMessage("Exporting");
    try {
      const response = await fetch(`${API_BASE}/api/cases/${selectedCase.id}/export`);
      if (!response.ok) {
        throw new Error("Export failed");
      }
      setExportJson(JSON.stringify(await response.json(), null, 2));
      setMessage("Export ready");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Export failed");
    }
  }

  return (
    <main className="min-h-screen bg-[#f6f7f8] text-zinc-950">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-[1540px] flex-col gap-4 px-4 py-4 sm:px-6 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">
              LipiOCR Enterprise
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-normal">
              Nepal KYC Document Intelligence
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="inline-flex h-9 items-center gap-2 rounded-md border border-zinc-200 bg-zinc-50 px-3 font-medium text-zinc-700">
              <Activity size={16} />
              {message}
            </span>
            <span className="inline-flex h-9 items-center gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 font-medium text-blue-700">
              <Network size={16} />
              {aiHealth?.model ?? "gemma-4-26b-4bit"}
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
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric icon={<Building2 size={18} />} label="Cases" value={metrics.cases} />
            <Metric icon={<ClipboardCheck size={18} />} label="Review" value={metrics.review} />
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
              <Panel title="Validation Findings" icon={<ClipboardCheck size={16} />}>
                {selectedCase?.validation_findings.length ? (
                  <div className="space-y-2">
                    {selectedCase.validation_findings.map((finding, index) => (
                      <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm" key={index}>
                        <p className="font-semibold text-amber-800">{finding.code}</p>
                        <p className="mt-1 text-amber-700">{finding.message}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-zinc-500">No findings yet</p>
                )}
              </Panel>

              <Panel title="Integration" icon={<Network size={16} />}>
                <div className="space-y-3 text-sm">
                  <Info label="Modes" value={manifest?.modes.join(", ") ?? "Loading"} />
                  <Info label="Events" value={manifest?.events.slice(0, 4).join(", ") ?? "Loading"} />
                  <Info
                    label="Gemma"
                    value={`${aiHealth?.provider ?? "vllm"} · ${aiHealth?.enabled ? "remote enabled" : "local fallback"}`}
                  />
                </div>
              </Panel>

              <Panel title="Audit" icon={<History size={16} />}>
                {selectedCase?.audit_events.length ? (
                  <ol className="space-y-3">
                    {selectedCase.audit_events.map((event, index) => (
                      <li className="grid grid-cols-[88px_1fr] gap-3 text-xs" key={`${event.action}-${index}`}>
                        <span className="font-mono text-zinc-500">{formatDate(event.created_at)}</span>
                        <span>
                          <span className="block font-semibold">{event.action}</span>
                          <span className="block text-zinc-500">{event.actor}</span>
                        </span>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="text-sm text-zinc-500">No audit events</p>
                )}
              </Panel>

              <Panel
                title="Export"
                icon={
                  <button
                    className="inline-flex h-8 items-center gap-2 rounded-md border border-zinc-300 bg-white px-2.5 text-xs font-semibold hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={!selectedCase}
                    onClick={exportCase}
                    type="button"
                  >
                    <Download size={14} />
                    JSON
                  </button>
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
