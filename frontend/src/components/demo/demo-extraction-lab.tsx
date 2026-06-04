"use client";

import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowDownToLine,
  BadgeCheck,
  CalendarDays,
  CheckCircle2,
  FileJson,
  FileSearch,
  Fingerprint,
  Images,
  Languages,
  Loader2,
  MapPin,
  Pencil,
  RefreshCcw,
  Sparkles,
  UploadCloud,
  X,
} from "lucide-react";

import { LipiOcrLogo } from "@/components/brand/lipiocr-logo";
import { API_BASE, ApiRequestError, buildApiInit } from "@/lib/api-client";

type CorrectionCandidate = {
  suggested_value?: string;
  confidence?: number;
  audit_reason?: string;
};

type AddressResolution = {
  status?: string;
  province_name?: string;
  district_name?: string;
  local_level_name?: string;
  ward?: string;
};

type CalendarResolution = {
  source_calendar?: string;
  ad?: string;
  bs?: string;
};

type DocumentLanguageProfile = {
  nepali_chars?: number;
  english_chars?: number;
  digit_chars?: number;
  dominant_script?: string;
  has_nepali?: boolean;
  has_english?: boolean;
};

type DocumentUnderstanding = {
  document_type: string;
  detected_document_type: string;
  document_type_confidence: number;
  reason: string;
  signals_detected?: string[];
  language_profile?: DocumentLanguageProfile;
  content_hints?: string[];
  evidence_snippets?: string[];
  source_type?: string;
  signature_score?: number;
};

type DemoField = {
  key: string;
  label: string;
  label_en?: string;
  label_ne?: string;
  raw_value?: string;
  normalized_value?: string;
  value_en?: string;
  value_ne?: string;
  confidence?: number;
  source?: string;
  evidence_text?: string;
  audit_reason?: string;
  translation_status?: string;
  translation_reason?: string;
  correction_candidates?: CorrectionCandidate[];
  address_resolution?: AddressResolution | null;
  calendar?: CalendarResolution | null;
  page_number?: number;
};

type VisualAsset = {
  kind: string;
  label: string;
  image_uri: string;
  bbox?: number[];
  confidence?: number;
  source?: string;
  review_note?: string;
};

type DemoResult = {
  status: string;
  filename: string;
  document_type: string;
  document_understanding?: DocumentUnderstanding;
  summary: string;
  overall_confidence: number;
  fields: DemoField[];
  raw_text: string;
  warnings: string[];
  providers: string[];
  image_uri?: string;
  page_number?: number;
  pages?: DemoResult[];
  visual_assets?: VisualAsset[];
};

const sampleHints = [
  "Citizenship front/back photocopy",
  "ASBA or IPO application form",
  "Passport, national ID, license",
  "Bank onboarding or KYC form",
];

function confidenceLabel(confidence?: number) {
  const value = typeof confidence === "number" ? confidence : 0;
  if (value >= 0.85) return "High";
  if (value >= 0.65) return "Review";
  return "Needs check";
}

function confidenceClass(confidence?: number) {
  const value = typeof confidence === "number" ? confidence : 0;
  if (value >= 0.85) return "bg-emerald-50 text-emerald-700 ring-emerald-200";
  if (value >= 0.65) return "bg-amber-50 text-amber-700 ring-amber-200";
  return "bg-rose-50 text-rose-700 ring-rose-200";
}

function translationReasonLabel(value?: string) {
  switch (value) {
    case "transliterated_from_nepali":
      return "Transliterated from Nepali";
    case "lexicon_backfill":
      return "Backfilled from name lexicon";
    case "english_name_no_match":
      return "Name translation pending (low lexicon confidence)";
    case "address_normalization":
      return "Address normalized with Nepal locations";
    case "address_translation_missing":
      return "Address translation pending";
    case "not_language_field":
      return "Not language field";
    case "english_original":
      return "English-only field";
    case "missing":
      return "No input value";
    default:
      return "No translation rule";
  }
}

function formatPercent(value?: number) {
  const normalized = typeof value === "number" ? value : 0;
  return `${Math.round(normalized * 100)}%`;
}

function absoluteApiUrl(uri?: string) {
  if (!uri) return "";
  return uri.startsWith("http") ? uri : `${API_BASE}${uri}`;
}

function previewUrl(result: DemoResult | null) {
  return absoluteApiUrl(result?.image_uri);
}

function normalizeDocumentType(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function splitFields(fields: DemoField[]) {
  const structured = fields.filter((field) => !field.key.startsWith("ocr_line_"));
  const ocrLines = fields.filter((field) => field.key.startsWith("ocr_line_"));
  const bilingual = structured.filter((field) => field.value_en || field.value_ne);
  const derived = structured.filter((field) => field.calendar || field.address_resolution);
  return { structured, ocrLines, bilingual, derived };
}

export function DemoExtractionLab() {
  const [files, setFiles] = useState<File[]>([]);
  const [result, setResult] = useState<DemoResult | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [activePageIndex, setActivePageIndex] = useState(0);
  const [isExtracting, setIsExtracting] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const activePage = result?.pages?.[activePageIndex] ?? result;
  const activeFile = files[activePageIndex] ?? files[0] ?? null;
  const activeAssets = activePage?.visual_assets ?? [];
  const fieldGroups = useMemo(() => splitFields(activePage?.fields ?? result?.fields ?? []), [activePage, result]);
  const imagePreview = previewUrl(activePage);
  const understanding = activePage?.document_understanding ?? result?.document_understanding;
  const jsonPayload = useMemo(() => {
    if (!result) return "";
    return JSON.stringify(
      {
        ...result,
        fields: result.fields.map((field) => ({
          ...field,
          reviewer_value: edits[field.key] ?? field.normalized_value ?? "",
        })),
      },
      null,
      2,
    );
  }, [edits, result]);

  async function extract() {
    if (!files.length) {
      setError("Upload one or more document pages first.");
      return;
    }

    setIsExtracting(true);
    setError("");
    setResult(null);
    setEdits({});
    setActivePageIndex(0);
    try {
      const formData = new FormData();
      const multiple = files.length > 1;
      for (const selectedFile of files) {
        formData.append(multiple ? "files" : "file", selectedFile);
      }
      formData.append("prefer_lipicore", "true");
      const response = await fetch(
        `${API_BASE}${multiple ? "/api/demo/extract-pages" : "/api/demo/extract"}`,
        buildApiInit({ method: "POST", body: formData }),
      );
      if (!response.ok) {
        const detail = await response.text();
        throw new ApiRequestError(response.status, detail || "Extraction failed");
      }
      const payload = (await response.json()) as DemoResult;
      setResult(payload);
      const editableFields = payload.pages?.length ? payload.pages.flatMap((page) => page.fields) : payload.fields;
      setEdits(
        Object.fromEntries(
          editableFields.map((field) => [field.key, field.normalized_value || field.value_en || field.raw_value || ""]),
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Extraction failed");
    } finally {
      setIsExtracting(false);
    }
  }

  function downloadJson() {
    if (!jsonPayload) return;
    const blob = new Blob([jsonPayload], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${result?.filename || "lipiocr-demo"}-extraction.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function handleFileSelection(selected: FileList | null) {
    const nextFiles = Array.from(selected ?? []);
    setFiles(nextFiles);
    setResult(null);
    setEdits({});
    setError("");
    setActivePageIndex(0);
  }

  return (
    <>
    <main className="min-h-screen bg-[#f6f8fb] text-slate-950">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1800px] items-center justify-between gap-4 px-5 py-3">
          <Link href="/" className="shrink-0">
            <LipiOcrLogo size="sm" label="LipiOCR Demo" />
          </Link>
          <div className="hidden min-w-0 flex-1 items-center justify-center gap-2 text-xs font-semibold text-slate-500 md:flex">
            <Sparkles size={15} className="text-cyan-700" />
            Demo extraction lab for Nepali KYC and financial documents
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/dashboard"
              className="inline-flex h-9 items-center rounded-lg border border-slate-200 bg-white px-3 text-xs font-bold text-slate-700 hover:border-cyan-200 hover:text-cyan-700"
            >
              Platform
            </Link>
            <button
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-gradient-to-r from-cyan-700 to-teal-500 px-3 text-xs font-extrabold text-white shadow-[var(--shadow-button)] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!result}
              onClick={downloadJson}
              type="button"
            >
              <FileJson size={15} />
              Download JSON
            </button>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-[1800px] px-5 py-5">
        <div className="mb-4 grid gap-3 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-[var(--shadow-soft)]">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                <p className="text-xs font-bold uppercase tracking-[0.08em] text-cyan-700">Tomorrow demo mode</p>
                <h1 className="mt-1 text-2xl font-extrabold tracking-normal text-slate-950">Document intelligence first, then extraction</h1>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
                  This page runs document understanding before mapping fields: OCR intake, document classification, bilingual labeling,
                  cross-language normalization, BS/AD conversion, and original evidence retention.
                </p>
              </div>
              <button
                className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-lg bg-slate-950 px-4 text-sm font-extrabold text-white disabled:cursor-not-allowed disabled:opacity-60"
                disabled={!files.length || isExtracting}
                onClick={extract}
                type="button"
              >
                {isExtracting ? <Loader2 className="animate-spin" size={16} /> : <FileSearch size={16} />}
                {isExtracting ? "Extracting" : "Extract demo"}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-2 xl:grid-cols-4">
            <Metric
              title="Doc Understanding"
              value={result ? formatPercent(understanding?.document_type_confidence) : "Waiting"}
              icon={<Sparkles size={17} />}
            />
            <Metric title="Document" value={result ? normalizeDocumentType(result.document_type) : "Waiting"} icon={<FileSearch size={17} />} />
            <Metric title="Fields" value={String(fieldGroups.structured.length)} icon={<Pencil size={17} />} />
            <Metric title="Confidence" value={formatPercent(result?.overall_confidence)} icon={<BadgeCheck size={17} />} />
            <Metric title="Bilingual" value={String(fieldGroups.bilingual.length)} icon={<Languages size={17} />} />
          </div>
        </div>

        {error ? (
          <div className="mb-4 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm font-semibold text-rose-700">
            <AlertTriangle size={17} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        ) : null}

        <div className="grid gap-4 xl:grid-cols-[0.98fr_1.02fr]">
          <section className="min-h-[720px] rounded-xl border border-slate-200 bg-white shadow-[var(--shadow-soft)]">
            <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
              <div>
                <h2 className="text-sm font-extrabold text-slate-950">Document Preview</h2>
                <p className="text-xs font-medium text-slate-500">
                  {files.length ? `${files.length} page(s) selected` : "Upload one or more pages to start"}
                </p>
              </div>
              <button
                className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-xs font-bold text-slate-700 hover:border-cyan-200 hover:text-cyan-700"
                onClick={() => fileInputRef.current?.click()}
                type="button"
              >
                <UploadCloud size={15} />
                Choose pages
              </button>
              <input
                ref={fileInputRef}
                className="hidden"
                type="file"
                accept="image/*,.pdf,.txt"
                multiple
                onChange={(event) => handleFileSelection(event.target.files)}
              />
            </div>

            {!files.length ? (
              <button
                className="m-4 flex min-h-[500px] w-[calc(100%-2rem)] flex-col items-center justify-center rounded-xl border border-dashed border-cyan-300 bg-cyan-50/60 p-8 text-center hover:bg-cyan-50"
                onClick={() => fileInputRef.current?.click()}
                type="button"
              >
                <UploadCloud size={38} className="text-cyan-700" />
                <span className="mt-4 text-lg font-extrabold text-slate-950">Upload one document or multiple pages</span>
                <span className="mt-2 max-w-lg text-sm leading-6 text-slate-600">
                  Add citizenship front/back, photocopies, PDF pages, or supporting KYC forms. The demo keeps OCR evidence,
                  maps structured fields, and crops review assets where visible.
                </span>
                <span className="mt-5 flex flex-wrap justify-center gap-2">
                  {sampleHints.map((hint) => (
                    <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-slate-600 ring-1 ring-slate-200" key={hint}>
                      {hint}
                    </span>
                  ))}
                </span>
              </button>
            ) : (
              <div className="grid gap-4 p-4 lg:grid-cols-[1fr_0.8fr] xl:grid-cols-1 2xl:grid-cols-[1fr_0.72fr]">
                {result?.pages?.length ? (
                  <div className="flex flex-wrap gap-2 lg:col-span-2 xl:col-span-1 2xl:col-span-2">
                    {result.pages.map((page, index) => (
                      <button
                        className={`inline-flex h-9 items-center gap-2 rounded-lg border px-3 text-xs font-extrabold ${
                          index === activePageIndex
                            ? "border-cyan-300 bg-cyan-50 text-cyan-800"
                            : "border-slate-200 bg-white text-slate-600 hover:border-cyan-200"
                        }`}
                        key={`${page.filename}-${page.page_number ?? index}`}
                        onClick={() => setActivePageIndex(index)}
                        type="button"
                      >
                        <Images size={14} />
                        Page {page.page_number ?? index + 1}
                        <span className="font-semibold">{normalizeDocumentType(page.document_type)}</span>
                      </button>
                    ))}
                  </div>
                ) : null}
                <div className="relative flex min-h-[500px] items-center justify-center overflow-hidden rounded-xl border border-slate-200 bg-slate-100">
                  {imagePreview ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img alt="Uploaded document preview" className="max-h-[680px] w-full object-contain" src={imagePreview} />
                  ) : (
                    <div className="p-8 text-center">
                      <FileSearch size={36} className="mx-auto text-cyan-700" />
                      <p className="mt-3 text-sm font-bold text-slate-700">{activeFile?.name || "Selected page"}</p>
                      <p className="mt-1 text-xs text-slate-500">Preview is available for image uploads. PDF/text extraction still works.</p>
                    </div>
                  )}
                  {isExtracting ? (
                    <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-950/25">
                      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-cyan-400/20 to-transparent opacity-70" style={{ animation: "lipiocr-scan 1.8s linear infinite" }} />
                      <div className="absolute left-[6px] right-[6px] top-3 rounded border border-cyan-200/80 bg-cyan-50/50 px-3 py-2 text-xs font-bold text-cyan-900 shadow-[var(--shadow-soft)] backdrop-blur">
                        Scanning document and extracting fields...
                      </div>
                      <div className="absolute bottom-6 left-1/2 h-5 w-5 -translate-x-1/2 rounded-full border-4 border-cyan-300 border-t-transparent border-r-transparent animate-spin"></div>
                    </div>
                  ) : null}
                </div>

                <aside className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-extrabold uppercase tracking-[0.08em] text-slate-500">Raw OCR evidence</h3>
                    {result ? <span className="text-xs font-bold text-slate-500">{fieldGroups.ocrLines.length} lines</span> : null}
                  </div>
                  {activeAssets.length ? (
                    <div className="mt-3">
                      <div className="mb-2 flex items-center gap-2 text-xs font-extrabold uppercase tracking-[0.08em] text-slate-500">
                        <Fingerprint size={14} className="text-cyan-700" />
                        Visual assets
                      </div>
                      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1">
                        {activeAssets.map((asset) => (
                          <div className="rounded-lg border border-slate-200 bg-white p-2" key={`${asset.kind}-${asset.image_uri}`}>
                            <div className="flex items-center justify-between gap-2">
                              <p className="truncate text-xs font-extrabold text-slate-800">{asset.label}</p>
                              <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-extrabold ring-1 ${confidenceClass(asset.confidence)}`}>
                                {formatPercent(asset.confidence)}
                              </span>
                            </div>
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                              alt={asset.label}
                              className="mt-2 h-28 w-full rounded-md bg-slate-100 object-contain"
                              src={absoluteApiUrl(asset.image_uri)}
                            />
                            <p className="mt-2 text-[11px] leading-4 text-slate-500">{asset.review_note}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  <div className="mt-3 max-h-[650px] space-y-2 overflow-auto pr-1">
                    {result ? (
                      <>
                        {fieldGroups.ocrLines.length ? fieldGroups.ocrLines.map((field) => (
                          <div className="rounded-lg border border-slate-200 bg-white p-2 text-xs leading-5 text-slate-700" key={field.key}>
                            {field.raw_value}
                          </div>
                        )) : (
                          <pre className="whitespace-pre-wrap rounded-lg border border-slate-200 bg-white p-3 text-xs leading-5 text-slate-700">
                            {result.raw_text || "No OCR text returned."}
                          </pre>
                        )}
                      </>
                    ) : (
                      <p className="rounded-lg border border-slate-200 bg-white p-3 text-xs leading-5 text-slate-500">
                        OCR text will appear here after extraction, including lines that were not mapped to a known field.
                      </p>
                    )}
                  </div>
                </aside>
              </div>
            )}
          </section>

          <section className="min-h-[720px] rounded-xl border border-slate-200 bg-white shadow-[var(--shadow-soft)]">
            <div className="border-b border-slate-200 px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-extrabold text-slate-950">Extracted Data</h2>
                  <p className="text-xs font-medium text-slate-500">Editable reviewer values with original OCR evidence</p>
                </div>
                <button
                  className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-xs font-bold text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={!files.length || isExtracting}
                  onClick={extract}
                  type="button"
                >
                  <RefreshCcw size={14} />
                  Re-extract
                </button>
              </div>
            </div>

            {!result ? (
              <div className="grid min-h-[620px] place-items-center p-8 text-center">
                <div className="max-w-md">
                  <Languages size={38} className="mx-auto text-cyan-700" />
                  <h3 className="mt-4 text-lg font-extrabold text-slate-950">Bilingual field pairing</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-600">
                    Extracted fields will show Nepali, English, normalized reviewer value, confidence, and audit reason
                    in one place.
                  </p>
                </div>
              </div>
            ) : (
                  <div className="grid gap-4 p-4 2xl:grid-cols-[1fr_0.52fr]">
                <div>
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <StatusPill icon={<CheckCircle2 size={14} />} label={result.summary} />
                    {result.providers.slice(0, 4).map((provider) => (
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600" key={provider}>
                        {provider}
                      </span>
                    ))}
                  </div>

                  <div className="mb-3 rounded-xl border border-cyan-200 bg-cyan-50 p-3">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <p className="text-sm font-extrabold text-cyan-900">
                        Document understanding
                      </p>
                      <span className="rounded-full bg-white px-2 py-0.5 text-xs font-bold text-cyan-700">
                        {understanding?.source_type === "heuristic_signature" ? "Template signal found" : "Content-based"}
                      </span>
                    </div>
                    <p className="text-xs font-semibold text-slate-700">
                      {understanding?.reason ?? "Understanding output is not available yet."}
                    </p>
                    {understanding ? (
                      <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
                        <span className="rounded-lg bg-white p-2 text-slate-700">
                          Detect:
                          {" "}
                          <b>{normalizeDocumentType(understanding.detected_document_type)}</b>
                        </span>
                        <span className="rounded-lg bg-white p-2 text-slate-700">
                          Signature score: <b>{understanding.signature_score ?? 0}</b>
                        </span>
                        {understanding.language_profile ? (
                          <span className="rounded-lg bg-white p-2 text-slate-700">
                            Script: <b>{understanding.language_profile.dominant_script || "unknown"}</b>
                          </span>
                        ) : null}
                        {understanding.language_profile ? (
                          <span className="rounded-lg bg-white p-2 text-slate-700">
                            Chars:
                            <b>
                              {" "}
                              {understanding.language_profile.nepali_chars ?? 0}N /
                              {understanding.language_profile.english_chars ?? 0}E /
                              {understanding.language_profile.digit_chars ?? 0}D
                            </b>
                          </span>
                        ) : null}
                        {understanding.signals_detected?.length ? (
                          <span className="rounded-lg bg-white p-2 text-slate-700 sm:col-span-2">
                            Signals:
                            <b> {understanding.signals_detected.slice(0, 5).join(", ")}</b>
                          </span>
                        ) : null}
                        {understanding.content_hints?.length ? (
                          <span className="rounded-lg bg-white p-2 text-slate-700 sm:col-span-2">
                            Extracted content snippets:
                            <ul className="mt-1 space-y-1">
                              {understanding.content_hints.slice(0, 4).map((hint) => (
                                <li className="truncate" key={hint}>
                                  • {hint}
                                </li>
                              ))}
                            </ul>
                          </span>
                        ) : null}
                      </div>
                    ) : null}
                  </div>

                  {result.warnings.length ? (
                    <div className="mb-3 space-y-2">
                      {result.warnings.map((warning) => (
                        <div className="flex gap-2 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs font-semibold text-amber-800" key={warning}>
                          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                          <span>{warning}</span>
                        </div>
                      ))}
                    </div>
                  ) : null}

                  <div className="overflow-hidden rounded-xl border border-slate-200">
                    <div className="grid grid-cols-[1.25fr_1.35fr_0.62fr] border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs font-extrabold text-slate-500">
                      <span>Field</span>
                      <span>Reviewer value</span>
                      <span>Confidence</span>
                    </div>
                    <div className="max-h-[710px] divide-y divide-slate-100 overflow-auto">
                      {fieldGroups.structured.map((field) => (
                        <FieldRow
                          field={field}
                          key={field.key}
                          value={edits[field.key] ?? ""}
                          onChange={(value) => setEdits((current) => ({ ...current, [field.key]: value }))}
                        />
                      ))}
                    </div>
                  </div>
                </div>

                <aside className="space-y-3">
                  <InsightCard
                    icon={<Languages size={16} />}
                    title="Bilingual values"
                    items={fieldGroups.bilingual.slice(0, 8).map((field) => ({
                      label: field.label_en || field.label,
                      value: `${field.value_ne || "Nepali pending"} / ${field.value_en || "English pending"}`,
                    }))}
                  />
                  <InsightCard
                    icon={<Sparkles size={16} />}
                    title="Reasoning"
                    items={fieldGroups.structured
                      .filter((field) => field.translation_status && field.translation_status !== "not_language_field")
                      .slice(0, 6)
                      .map((field) => ({
                        label: field.label_en || field.label,
                        value: `${translationReasonLabel(field.translation_status)} · ${field.translation_reason || field.audit_reason || "No rule"}`,
                      }))}
                  />
                  <InsightCard
                    icon={<CalendarDays size={16} />}
                    title="Date conversions"
                    items={fieldGroups.derived
                      .filter((field) => field.calendar)
                      .slice(0, 5)
                      .map((field) => ({
                        label: field.label_en || field.label,
                        value: `${field.calendar?.bs || "-"} BS · ${field.calendar?.ad || "-"} AD`,
                      }))}
                  />
                  <InsightCard
                    icon={<MapPin size={16} />}
                    title="Address matches"
                    items={fieldGroups.derived
                      .filter((field) => field.address_resolution)
                      .slice(0, 5)
                      .map((field) => ({
                        label: field.label_en || field.label,
                        value: [
                          field.address_resolution?.local_level_name,
                          field.address_resolution?.ward ? `Ward ${field.address_resolution.ward}` : "",
                          field.address_resolution?.district_name,
                        ]
                          .filter(Boolean)
                          .join(", ") || "No registry match",
                      }))}
                  />
                  <div className="rounded-xl border border-slate-200 bg-slate-950 p-3 text-white">
                    <div className="flex items-center gap-2 text-sm font-extrabold">
                      <ArrowDownToLine size={16} className="text-cyan-200" />
                      Export shape
                    </div>
                    <pre className="mt-3 max-h-[210px] overflow-auto whitespace-pre-wrap rounded-lg bg-black/30 p-3 text-[11px] leading-5 text-cyan-50">
                      {jsonPayload.slice(0, 1800)}
                      {jsonPayload.length > 1800 ? "\n..." : ""}
                    </pre>
                  </div>
                </aside>
              </div>
            )}
          </section>
        </div>
      </section>
    </main>
      <style jsx>{`
        @keyframes lipiocr-scan {
          0% {
            transform: translateY(-110%);
            opacity: 0;
          }
          12% {
            opacity: 0.9;
          }
          50% {
            opacity: 0.95;
          }
          88% {
            opacity: 0.9;
          }
          100% {
            transform: translateY(110%);
            opacity: 0;
          }
        }
      `}</style>
    </>
  );
}

function Metric({ title, value, icon }: { title: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-[var(--shadow-soft)]">
      <div className="flex items-center gap-2 text-xs font-bold text-slate-500">
        <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-50 text-cyan-700">{icon}</span>
        {title}
      </div>
      <p className="mt-2 truncate text-xl font-extrabold text-slate-950">{value}</p>
    </div>
  );
}

function StatusPill({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700 ring-1 ring-emerald-200">
      {icon}
      {label}
    </span>
  );
}

function FieldRow({
  field,
  value,
  onChange,
}: {
  field: DemoField;
  value: string;
  onChange: (value: string) => void;
}) {
  const candidates = field.correction_candidates ?? [];
  return (
      <div className="grid grid-cols-[1.25fr_1.35fr_0.62fr] gap-3 px-3 py-3 text-sm">
      <div className="min-w-0">
        <div className="flex items-start gap-2">
          <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded bg-cyan-600 text-[10px] font-extrabold text-white">
            {field.key.startsWith("ocr_line_") ? "O" : "F"}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-extrabold text-slate-950">{field.label_en || field.label}</p>
            <p className="truncate text-xs font-semibold text-slate-500">{field.label_ne || field.key}</p>
          </div>
        </div>
        <p className="mt-2 rounded-lg bg-slate-50 p-2 text-xs leading-5 text-slate-600">
          Original: <span className="font-semibold text-slate-800">{field.raw_value || "-"}</span>
        </p>
        {field.evidence_text && field.evidence_text !== field.raw_value ? (
          <p className="mt-1 truncate text-[11px] font-medium text-slate-400">Evidence: {field.evidence_text}</p>
        ) : null}
      </div>

      <div className="min-w-0">
        <input
          className="h-9 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-950 outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
          onChange={(event) => onChange(event.target.value)}
          value={value}
        />
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          <TinyValue label="English" value={field.value_en || "-"} />
          <TinyValue label="Nepali" value={field.value_ne || "-"} />
        </div>
        {candidates.length ? (
          <div className="mt-2 flex items-center gap-2">
            <select
              className="h-8 min-w-0 flex-1 rounded-lg border border-cyan-200 bg-cyan-50 px-2 text-xs font-bold text-cyan-800 outline-none"
              onChange={(event) => event.target.value && onChange(event.target.value)}
              value=""
            >
              <option value="">Possible correction</option>
              {candidates.map((candidate) => (
                <option key={`${candidate.suggested_value}-${candidate.confidence}`} value={candidate.suggested_value || ""}>
                  {candidate.suggested_value} · {formatPercent(candidate.confidence)}
                </option>
              ))}
            </select>
            <button
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:border-rose-200 hover:text-rose-600"
              onClick={() => onChange(field.normalized_value || field.raw_value || "")}
              title="Reset value"
              type="button"
            >
              <X size={14} />
            </button>
          </div>
        ) : null}
      </div>

      <div className="min-w-0">
        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-extrabold ring-1 ${confidenceClass(field.confidence)}`}>
          {confidenceLabel(field.confidence)} · {formatPercent(field.confidence)}
        </span>
        <p className="mt-2 text-xs font-semibold leading-5 text-slate-500">
          Reasoning: {field.translation_reason || field.audit_reason || field.source}
        </p>
        <p className="mt-1 rounded-lg bg-cyan-50 px-2 py-1 text-xs font-bold text-cyan-700">
          {translationReasonLabel(field.translation_status)} · {field.confidence ? formatPercent(field.confidence) : ""}
        </p>
        {field.calendar ? (
          <p className="mt-2 rounded-lg bg-blue-50 p-2 text-xs font-bold leading-5 text-blue-700">
            {field.calendar.bs || "-"} BS
            <br />
            {field.calendar.ad || "-"} AD
          </p>
        ) : null}
        {field.address_resolution ? (
          <p className="mt-2 rounded-lg bg-emerald-50 p-2 text-xs font-bold leading-5 text-emerald-700">
            {field.address_resolution.status || "address"}
          </p>
        ) : null}
      </div>
    </div>
  );
}

function TinyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg bg-slate-50 px-2 py-1.5">
      <p className="text-[10px] font-bold uppercase text-slate-400">{label}</p>
      <p className="truncate text-xs font-bold text-slate-700">{value}</p>
    </div>
  );
}

function InsightCard({
  icon,
  title,
  items,
}: {
  icon: React.ReactNode;
  title: string;
  items: { label: string; value: string }[];
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3">
      <div className="flex items-center gap-2 text-sm font-extrabold text-slate-950">
        <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-50 text-cyan-700">{icon}</span>
        {title}
      </div>
      <div className="mt-3 space-y-2">
        {items.length ? (
          items.map((item) => (
            <div className="rounded-lg bg-slate-50 p-2" key={`${item.label}-${item.value}`}>
              <p className="truncate text-xs font-bold text-slate-600">{item.label}</p>
              <p className="mt-0.5 text-xs leading-5 text-slate-500">{item.value}</p>
            </div>
          ))
        ) : (
          <p className="rounded-lg bg-slate-50 p-2 text-xs leading-5 text-slate-500">No values detected yet.</p>
        )}
      </div>
    </section>
  );
}
