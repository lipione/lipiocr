"use client";

import { FileCog, FileSearch, FileText, Layers3, Loader2, Plus, Save, ShieldCheck, Trash2, Upload } from "lucide-react";
import { FormEvent, PointerEvent as ReactPointerEvent, ReactNode, RefObject } from "react";

import { API_BASE } from "../../lib/api-client";
import type { TemplateDragMode } from "../../lib/template-canvas";
import type {
  DocumentType,
  OcrPage,
  ResourceState,
  TemplateDraft,
  TemplateDragState,
  TemplateProfileField,
  TemplateProfilePage,
  TemplateStudio,
} from "../../types/workspace";

const templateDocumentTypes: { value: DocumentType; label: string }[] = [
  { value: "unknown", label: "Auto" },
  { value: "citizenship", label: "Citizenship" },
  { value: "national_id", label: "National ID" },
  { value: "asba_application", label: "ASBA" },
  { value: "account_opening", label: "Account Form" },
  { value: "passport", label: "Passport" },
  { value: "driving_license", label: "License" },
];

const templateFieldTypes = ["text", "name", "address", "date", "amount", "number", "phone", "email", "checkbox", "table", "photo", "signature"];

const templateResizeHandles: { mode: Exclude<TemplateDragMode, "move">; className: string }[] = [
  { mode: "resize-nw", className: "-left-1.5 -top-1.5 cursor-nwse-resize" },
  { mode: "resize-ne", className: "-right-1.5 -top-1.5 cursor-nesw-resize" },
  { mode: "resize-sw", className: "-bottom-1.5 -left-1.5 cursor-nesw-resize" },
  { mode: "resize-se", className: "-bottom-1.5 -right-1.5 cursor-nwse-resize" },
];

export type TemplateStudioPanelProps = {
  busy: boolean;
  activeAction: string | null;
  templateName: string;
  templateDocumentType: DocumentType;
  templateFiles: File[];
  templateDraft: TemplateDraft | null;
  selectedTemplatePage: TemplateProfilePage | null;
  selectedTemplateField: TemplateProfileField | null;
  selectedTemplatePageFields: TemplateProfileField[];
  templateStudio: ResourceState<TemplateStudio>;
  templateCanvasRef: RefObject<HTMLDivElement | null>;
  templateDrag: TemplateDragState | null;
  setTemplateName: (value: string) => void;
  setTemplateDocumentType: (value: DocumentType) => void;
  setTemplateFiles: (files: File[]) => void;
  setSelectedTemplatePageNumber: (value: number) => void;
  setSelectedTemplateFieldId: (value: string | null) => void;
  uploadTemplateDraft: (event: FormEvent<HTMLFormElement>) => void;
  addTemplateField: () => void;
  updateTemplateField: (fieldId: string, patch: Partial<TemplateProfileField>) => void;
  updateTemplateFieldBbox: (fieldId: string, index: number, value: string) => void;
  deleteTemplateField: (fieldId: string) => void;
  saveTemplateDraft: () => void;
  publishTemplateDraft: () => void;
  startTemplateFieldDrag: (event: ReactPointerEvent<HTMLElement>, field: TemplateProfileField, mode: TemplateDragMode) => void;
};

export function TemplateStudioPanel({
  activeAction,
  addTemplateField,
  busy,
  deleteTemplateField,
  publishTemplateDraft,
  saveTemplateDraft,
  selectedTemplateField,
  selectedTemplatePage,
  selectedTemplatePageFields,
  setSelectedTemplateFieldId,
  setSelectedTemplatePageNumber,
  setTemplateDocumentType,
  setTemplateFiles,
  setTemplateName,
  startTemplateFieldDrag,
  templateCanvasRef,
  templateDocumentType,
  templateDraft,
  templateDrag,
  templateFiles,
  templateName,
  templateStudio,
  updateTemplateField,
  updateTemplateFieldBbox,
  uploadTemplateDraft,
}: TemplateStudioPanelProps) {
  const templateFileLabel =
    templateFiles.length === 0
      ? "Choose template pages"
      : templateFiles.length === 1
        ? templateFiles[0].name
        : `${templateFiles.length} pages selected`;

  return (
    <TemplatePanel title="Template Creation Studio" icon={<FileCog size={16} />}>
      <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-4">
          <form className="rounded-2xl border border-cyan-100 bg-cyan-50/40 p-3" onSubmit={uploadTemplateDraft}>
            <TemplateSectionLabel icon={<Upload size={15} />} label="Upload Template Pages" />
            <label className="block text-xs font-bold text-slate-600">
              Template name
              <input
                className="mt-1 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                onChange={(event) => setTemplateName(event.target.value)}
                value={templateName}
              />
            </label>
            <div className="mt-3">
              <p className="mb-2 text-xs font-bold text-slate-600">Document family</p>
              <TemplateSegmentedPicker
                ariaLabel="Template document type"
                compact
                options={templateDocumentTypes}
                value={templateDocumentType}
                onChange={(value) => setTemplateDocumentType(value as DocumentType)}
              />
            </div>
            <label className="mt-3 flex min-h-24 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-cyan-200 bg-white px-3 text-center text-sm font-bold text-cyan-700 transition hover:-translate-y-0.5 hover:border-cyan-400">
              <Upload size={18} />
              <span className="mt-2">{templateFileLabel}</span>
              <span className="mt-1 text-xs font-medium text-slate-500">Front/back IDs, forms, PDFs, or page images</span>
              <input
                className="sr-only"
                multiple
                onChange={(event) => setTemplateFiles(Array.from(event.target.files ?? []))}
                type="file"
              />
            </label>
            <TemplateActionButton
              busy={activeAction === "template-upload"}
              className="mt-3 w-full"
              disabled={busy || !templateFiles.length}
              icon={<FileSearch size={14} />}
              type="submit"
              tone="primary"
            >
              Auto Map Fields
            </TemplateActionButton>
          </form>

          {templateDraft ? (
            <div className="rounded-2xl border border-cyan-100 bg-white p-3 text-xs">
              <TemplateSectionLabel icon={<FileSearch size={15} />} label="Auto Mapping" />
              <div className="grid gap-2">
                <TemplateSignal label="Detected family" score={templateDraft.document_type_confidence} value={labelize(templateDraft.document_type)} />
                <TemplateSignal label="Template quality" score={templateDraft.quality_score} value={qualityLabel(templateDraft.quality_score)} />
              </div>
              {templateDraft.document_type_reason ? (
                <p className="mt-2 rounded-xl bg-slate-50 px-3 py-2 text-slate-600">{templateDraft.document_type_reason}</p>
              ) : null}
            </div>
          ) : null}

          <div className="rounded-2xl border border-slate-200 p-3">
            <TemplateSectionLabel icon={<Layers3 size={15} />} label="Pages" />
            <div className="grid gap-2">
              {templateDraft?.pages.length ? (
                templateDraft.pages.map((page) => {
                  const active = page.page_number === selectedTemplatePage?.page_number;
                  const pageFieldCount = templateDraft.fields.filter((field) => field.page_number === page.page_number).length;
                  return (
                    <button
                      className={`rounded-xl border p-3 text-left text-xs transition ${
                        active
                          ? "border-cyan-500 bg-cyan-50 text-cyan-950"
                          : "border-slate-200 bg-white hover:border-cyan-200 hover:bg-slate-50"
                      }`}
                      key={page.id}
                      onClick={() => {
                        setSelectedTemplatePageNumber(page.page_number);
                        setSelectedTemplateFieldId(
                          templateDraft.fields.find((field) => field.page_number === page.page_number)?.id ?? null,
                        );
                      }}
                      type="button"
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="truncate font-bold">Page {page.page_number}</span>
                        <span className="font-mono">{pageFieldCount}</span>
                      </span>
                      <span className="mt-1 block truncate text-slate-500">{page.filename}</span>
                    </button>
                  );
                })
              ) : (
                <p className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500">
                  Upload pages to start a template draft.
                </p>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 p-3">
            <div className="flex items-center justify-between gap-2">
              <TemplateSectionLabel icon={<FileText size={15} />} label="Published Profiles" />
              <span className="font-mono text-xs text-slate-500">{templateStudio.data?.profiles?.length ?? 0}</span>
            </div>
            <div className="space-y-2">
              {(templateStudio.data?.profiles ?? []).slice(0, 5).map((profile) => (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs" key={profile.id}>
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate font-bold">{profile.name}</p>
                    <TemplateStatusBadge status={profile.status} />
                  </div>
                  <p className="mt-1 truncate text-slate-500">
                    {profile.page_count} pages · {profile.field_count} fields · v{profile.version}
                    {profile.quality_score !== undefined ? ` · ${pct(profile.quality_score)} quality` : ""}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="min-w-0 space-y-3">
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <TemplateInfo label="Draft" value={templateDraft ? labelize(templateDraft.status) : "None"} />
            <TemplateInfo label="Pages" value={`${templateDraft?.pages.length ?? 0}`} />
            <TemplateInfo label="Fields" value={`${templateDraft?.fields.length ?? 0}`} />
            <TemplateInfo label="Quality" value={templateDraft ? pct(templateDraft.quality_score) : "0%"} />
          </div>
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-100">
            <div className="border-b border-slate-200 bg-white p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-xs font-bold uppercase text-slate-500">Canvas Editor</p>
                  <p className="mt-1 truncate text-sm font-bold text-slate-950">
                    {selectedTemplatePage ? `Page ${selectedTemplatePage.page_number} · ${selectedTemplatePage.filename}` : "No page selected"}
                  </p>
                </div>
                <TemplateActionButton disabled={!templateDraft || !selectedTemplatePage} icon={<Plus size={14} />} onClick={addTemplateField}>
                  Add Box
                </TemplateActionButton>
              </div>
            </div>
            <div
              className="relative mx-auto min-h-[460px] w-full overflow-hidden bg-white"
              ref={templateCanvasRef}
              style={{ aspectRatio: pageAspectRatio(selectedTemplatePage) }}
            >
              {selectedTemplatePage?.image_uri ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  alt={`${selectedTemplatePage.filename} template page`}
                  className="absolute inset-0 h-full w-full object-contain"
                  draggable={false}
                  src={sourceImageUrl(selectedTemplatePage.image_uri) ?? ""}
                />
              ) : selectedTemplatePage ? (
                <div className="absolute inset-0 p-5 text-xs text-slate-600">
                  {selectedTemplatePage.blocks.slice(0, 18).map((block, index) => (
                    <p className="mb-2 rounded-lg bg-slate-50 px-3 py-2" key={`${block.text}-${index}`}>
                      {block.text}
                    </p>
                  ))}
                </div>
              ) : (
                <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-500">
                  Upload template pages to see the canvas.
                </div>
              )}
              {selectedTemplatePage
                ? selectedTemplatePageFields.map((field) => {
                    const active = field.id === selectedTemplateField?.id;
                    const dragging = templateDrag?.fieldId === field.id;
                    return (
                      <div
                        aria-label={`${field.label} field box`}
                        className={`absolute touch-none rounded-[4px] border text-left transition ${
                          active
                            ? "border-cyan-600 bg-cyan-300/15 shadow-[0_0_0_2px_rgba(14,165,168,0.2)]"
                            : "border-emerald-500/70 bg-emerald-300/10 hover:border-cyan-500"
                        } ${dragging ? "cursor-grabbing" : "cursor-grab"}`}
                        key={field.id}
                        onClick={(event) => {
                          event.stopPropagation();
                          setSelectedTemplateFieldId(field.id);
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            setSelectedTemplateFieldId(field.id);
                          }
                        }}
                        onPointerDown={(event) => startTemplateFieldDrag(event, field, "move")}
                        role="button"
                        style={bboxStyle(field.bbox, selectedTemplatePage)}
                        tabIndex={0}
                        title={`${field.label} · ${field.key}`}
                      >
                        <span className="m-1 inline-block max-w-[90%] truncate rounded bg-white/90 px-1.5 py-0.5 text-[10px] font-bold text-slate-900 shadow-sm">
                          {field.label}
                        </span>
                        {active
                          ? templateResizeHandles.map((handle) => (
                              <span
                                aria-hidden="true"
                                className={`absolute h-3 w-3 rounded-full border-2 border-white bg-cyan-600 shadow-[0_2px_8px_rgba(14,165,168,0.35)] ${handle.className}`}
                                key={handle.mode}
                                onPointerDown={(event) => startTemplateFieldDrag(event, field, handle.mode)}
                              />
                            ))
                          : null}
                      </div>
                    );
                  })
                : null}
            </div>
          </div>
        </div>

        <div className="min-w-0 space-y-4">
          <div className="rounded-2xl border border-slate-200 p-3">
            <div className="flex items-center justify-between gap-2">
              <TemplateSectionLabel icon={<FileSearch size={15} />} label="Fields" />
              <span className="font-mono text-xs text-slate-500">{selectedTemplatePageFields.length}</span>
            </div>
            <div className="max-h-64 space-y-2 overflow-auto">
              {selectedTemplatePageFields.length ? (
                selectedTemplatePageFields.map((field) => (
                  <button
                    className={`block w-full rounded-xl border p-3 text-left text-xs ${
                      field.id === selectedTemplateField?.id
                        ? "border-cyan-500 bg-cyan-50"
                        : "border-slate-200 bg-white hover:border-cyan-200"
                    }`}
                    key={field.id}
                    onClick={() => setSelectedTemplateFieldId(field.id)}
                    type="button"
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate font-bold">{field.label}</span>
                      <span className="rounded-full bg-slate-100 px-2 py-1 font-mono">{pct(field.confidence)}</span>
                    </span>
                    <span className="mt-1 block truncate font-mono text-slate-500">{field.key}</span>
                    {field.detection_source ? (
                      <span className="mt-2 inline-flex max-w-full rounded-full bg-white px-2 py-1 font-bold text-slate-500">
                        <span className="truncate">{labelize(field.detection_source)}</span>
                      </span>
                    ) : null}
                  </button>
                ))
              ) : (
                <p className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500">
                  No fields mapped on this page yet.
                </p>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 p-3">
            <TemplateSectionLabel icon={<FileCog size={15} />} label="Field Inspector" />
            {selectedTemplateField ? (
              <div className="space-y-3">
                <label className="block text-xs font-bold text-slate-600">
                  Label
                  <input
                    className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm font-semibold outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                    onChange={(event) =>
                      updateTemplateField(selectedTemplateField.id, {
                        label: event.target.value,
                        key: selectedTemplateField.key === "new_field" ? fieldKeyFromLabel(event.target.value) : selectedTemplateField.key,
                      })
                    }
                    value={selectedTemplateField.label}
                  />
                </label>
                <label className="block text-xs font-bold text-slate-600">
                  Export key
                  <input
                    className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 font-mono text-sm outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                    onChange={(event) => updateTemplateField(selectedTemplateField.id, { key: fieldKeyFromLabel(event.target.value) })}
                    value={selectedTemplateField.key}
                  />
                </label>
                <div>
                  <p className="mb-2 text-xs font-bold text-slate-600">Field type</p>
                  <div className="grid grid-cols-3 gap-1.5">
                    {templateFieldTypes.map((fieldType) => {
                      const active = selectedTemplateField.type === fieldType;
                      return (
                        <button
                          className={`h-8 rounded-lg border px-2 text-xs font-bold ${
                            active
                              ? "border-cyan-600 bg-cyan-600 text-white"
                              : "border-slate-200 bg-white text-slate-600 hover:border-cyan-200"
                          }`}
                          key={fieldType}
                          onClick={() => updateTemplateField(selectedTemplateField.id, { type: fieldType })}
                          type="button"
                        >
                          {labelize(fieldType)}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <label className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-bold text-slate-700">
                  Required field
                  <input
                    checked={selectedTemplateField.required}
                    className="h-4 w-4 accent-cyan-600"
                    onChange={(event) => updateTemplateField(selectedTemplateField.id, { required: event.target.checked })}
                    type="checkbox"
                  />
                </label>
                <div>
                  <p className="mb-2 text-xs font-bold text-slate-600">Box coordinates</p>
                  <div className="grid grid-cols-4 gap-2">
                    {selectedTemplateField.bbox.map((value, index) => (
                      <input
                        className="h-9 min-w-0 rounded-lg border border-slate-200 px-2 font-mono text-xs outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                        key={`${selectedTemplateField.id}-bbox-${index}`}
                        onChange={(event) => updateTemplateFieldBbox(selectedTemplateField.id, index, event.target.value)}
                        value={value}
                      />
                    ))}
                  </div>
                </div>
                <label className="block text-xs font-bold text-slate-600">
                  Extraction hint
                  <textarea
                    className="mt-1 min-h-16 w-full resize-y rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                    onChange={(event) => updateTemplateField(selectedTemplateField.id, { extraction_hint: event.target.value })}
                    value={selectedTemplateField.extraction_hint}
                  />
                </label>
                {selectedTemplateField.detection_reason ? (
                  <div className="rounded-xl border border-cyan-100 bg-cyan-50 px-3 py-2 text-xs text-cyan-900">
                    <p className="font-extrabold">Auto-map reason</p>
                    <p className="mt-1 leading-5">{selectedTemplateField.detection_reason}</p>
                  </div>
                ) : null}
                <TemplateActionButton
                  className="w-full"
                  icon={<Trash2 size={14} />}
                  onClick={() => deleteTemplateField(selectedTemplateField.id)}
                >
                  Delete Field
                </TemplateActionButton>
              </div>
            ) : (
              <p className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-500">
                Select a field box or add a new one.
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2">
            <TemplateActionButton
              busy={activeAction === "template-save"}
              disabled={busy || !templateDraft}
              icon={<Save size={14} />}
              onClick={saveTemplateDraft}
            >
              Save Draft
            </TemplateActionButton>
            <TemplateActionButton
              busy={activeAction === "template-publish"}
              disabled={busy || !templateDraft || !templateDraft.fields.length}
              icon={<ShieldCheck size={14} />}
              onClick={publishTemplateDraft}
              tone="primary"
            >
              Publish
            </TemplateActionButton>
          </div>

          {templateDraft?.quality_checks?.length ? (
            <div className="rounded-2xl border border-slate-200 p-3">
              <TemplateSectionLabel icon={<ShieldCheck size={15} />} label="Publish Readiness" />
              <div className="grid gap-2">
                {templateDraft.quality_checks.map((check) => (
                  <div className={`rounded-xl border px-3 py-2 text-xs ${statusTone(check.status)}`} key={check.key}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-extrabold">{labelize(check.key)}</span>
                      <span className="font-mono">{labelize(check.status)}</span>
                    </div>
                    <p className="mt-1">{check.detail}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </TemplatePanel>
  );
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

function pageAspectRatio(page?: Pick<OcrPage, "width" | "height"> | null) {
  if (!page?.width || !page.height) {
    return "1 / 1.414";
  }
  return `${page.width} / ${page.height}`;
}

function bboxStyle(bbox: number[], page: Pick<OcrPage, "width" | "height">) {
  const [x1, y1, x2, y2] = bbox;
  return {
    left: `${(x1 / page.width) * 100}%`,
    top: `${(y1 / page.height) * 100}%`,
    width: `${((x2 - x1) / page.width) * 100}%`,
    height: `${((y2 - y1) / page.height) * 100}%`,
  };
}

function fieldKeyFromLabel(value: string) {
  return (
    value
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "") || "new_field"
  );
}

function labelize(value?: string) {
  return (value ?? "unknown").replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function pct(value?: number) {
  if (value === undefined || Number.isNaN(value)) {
    return "0%";
  }
  return `${Math.round(value * 100)}%`;
}

function qualityLabel(value?: number) {
  const score = value ?? 0;
  if (score >= 0.8) {
    return "Ready for test run";
  }
  if (score >= 0.65) {
    return "Review before publish";
  }
  return "Needs mapping";
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

function TemplatePanel({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
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

function TemplateSectionLabel({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <div className="mb-2 flex items-center gap-2 text-sm font-bold text-slate-950">
      <span className="rounded-lg bg-cyan-50 p-1.5 text-cyan-700">{icon}</span>
      <span>{label}</span>
    </div>
  );
}

function TemplateInfo({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs font-bold uppercase tracking-[0.1em] text-slate-500">{label}</p>
      <p className="mt-1 truncate text-sm font-bold text-slate-950">{value}</p>
    </div>
  );
}

function TemplateSignal({ label, score, value }: { label: string; score?: number; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
      <span className="min-w-0">
        <span className="block font-bold text-slate-900">{label}</span>
        <span className="block truncate text-slate-500">{value}</span>
      </span>
      <span className="font-mono font-extrabold text-cyan-700">{pct(score)}</span>
    </div>
  );
}

function TemplateStatusBadge({ status }: { status?: string }) {
  return (
    <span className={`inline-flex max-w-full items-center rounded-lg border px-2.5 py-1 text-xs font-bold ${statusTone(status)}`}>
      <span className="truncate">{labelize(status)}</span>
    </span>
  );
}

function TemplateSegmentedPicker({
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
    <div aria-label={ariaLabel} className={`grid gap-2 ${compact ? "grid-cols-2" : "grid-cols-1"}`} role="radiogroup">
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

function TemplateActionButton({
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
