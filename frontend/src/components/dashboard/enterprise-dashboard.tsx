"use client";

import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  Boxes,
  CheckCircle2,
  ClipboardCheck,
  Database,
  FileCog,
  FileSearch,
  Fingerprint,
  Gauge,
  GitBranch,
  Landmark,
  Layers3,
  LockKeyhole,
  Network,
  RefreshCcw,
  Route,
  SearchCheck,
  ShieldCheck,
  Upload,
  Workflow,
} from "lucide-react";
import type { ReactNode } from "react";

import type {
  AccuracyAnalytics,
  DocumentRecord,
  IntegrationOperations,
  KycCase,
  OcrPipelineProfile,
  OperationsDashboard,
  OperationsLane,
  PlatformStatus,
  ProcessingJob,
  ResourceState,
  TemplateStudio,
} from "../../types/workspace";

type EnterpriseDashboardProps = {
  accuracy: ResourceState<AccuracyAnalytics>;
  cases: KycCase[];
  exportProfiles: string[];
  integrationOps: ResourceState<IntegrationOperations>;
  jobs: ProcessingJob[];
  ocrPipeline: ResourceState<OcrPipelineProfile>;
  operations: ResourceState<OperationsDashboard>;
  platform: ResourceState<PlatformStatus>;
  selectedCase: KycCase | null;
  standaloneDocuments: DocumentRecord[];
  templateStudio: ResourceState<TemplateStudio>;
};

type MetricTone = "cyan" | "emerald" | "amber" | "rose" | "slate";

const toneClasses: Record<MetricTone, string> = {
  amber: "border-amber-200 bg-amber-50 text-amber-950",
  cyan: "border-cyan-200 bg-cyan-50 text-cyan-950",
  emerald: "border-emerald-200 bg-emerald-50 text-emerald-950",
  rose: "border-rose-200 bg-rose-50 text-rose-950",
  slate: "border-slate-200 bg-slate-50 text-slate-950",
};

const iconToneClasses: Record<MetricTone, string> = {
  amber: "bg-amber-100 text-amber-700",
  cyan: "bg-cyan-100 text-cyan-700",
  emerald: "bg-emerald-100 text-emerald-700",
  rose: "bg-rose-100 text-rose-700",
  slate: "bg-slate-100 text-slate-700",
};

function labelize(value?: string | null) {
  return (value ?? "unknown").replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

function pct(value?: number | null) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return value <= 1 ? `${Math.round(value * 100)}%` : `${Math.round(value)}%`;
}

function compactId(value?: string | null) {
  if (!value) {
    return "none";
  }
  return value.length > 18 ? `${value.slice(0, 8)}...${value.slice(-6)}` : value;
}

function formatDate(value?: string | null) {
  if (!value) {
    return "not updated";
  }
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function statusTone(status?: string) {
  const value = (status ?? "").toLowerCase();
  if (["approved", "configured", "passed", "clean", "ready", "verified", "completed", "exported"].includes(value)) {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (["partial", "warning", "review_required", "needs_review", "missing", "not_configured", "queued"].includes(value)) {
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

function providerLabel(provider: { key: string; label: string }) {
  if (provider.key === "gemma_vision") {
    return "LipiCore handwriting and print";
  }
  if (provider.key === "mock") {
    return "LipiCore local profile";
  }
  return "LipiCore recognition";
}

function providerBestFor(provider: { key: string; best_for: string }) {
  if (provider.key === "gemma_vision") {
    return "Nepali and English source text with reviewer confirmation";
  }
  if (provider.key === "mock") {
    return "Local workflow checks before institution data is connected";
  }
  return "Document text recognition with preserved page evidence";
}

function laneTone(laneKey: string): MetricTone {
  if (laneKey.includes("exception")) {
    return "rose";
  }
  if (laneKey.includes("review") || laneKey.includes("verification")) {
    return "amber";
  }
  if (laneKey.includes("export")) {
    return "emerald";
  }
  if (laneKey.includes("intake")) {
    return "cyan";
  }
  return "slate";
}

function fallbackLanes(cases: KycCase[]): OperationsLane[] {
  const intake = cases.filter((item) => ["created", "processing"].includes(item.status));
  const review = cases.filter((item) => item.status === "review_required");
  const exceptions = cases.filter(
    (item) => item.risk_level === "high" || item.validation_findings.some((finding) => finding.severity === "error"),
  );
  const exportReady = cases.filter((item) => ["approved", "exported"].includes(item.status));
  return [
    {
      key: "intake",
      label: "Intake",
      count: intake.length,
      description: "New uploads and OCR processing",
      case_ids: intake.slice(0, 8).map((item) => item.id),
    },
    {
      key: "review",
      label: "Review",
      count: review.length,
      description: "Maker-checker cases needing human decision",
      case_ids: review.slice(0, 8).map((item) => item.id),
    },
    {
      key: "exceptions",
      label: "Exceptions",
      count: exceptions.length,
      description: "High-risk, missing, or inconsistent evidence",
      case_ids: exceptions.slice(0, 8).map((item) => item.id),
    },
    {
      key: "export",
      label: "Export",
      count: exportReady.length,
      description: "Approved records ready for handoff",
      case_ids: exportReady.slice(0, 8).map((item) => item.id),
    },
  ];
}

export function EnterpriseDashboard({
  accuracy,
  cases,
  exportProfiles,
  integrationOps,
  jobs,
  ocrPipeline,
  operations,
  platform,
  selectedCase,
  standaloneDocuments,
  templateStudio,
}: EnterpriseDashboardProps) {
  const counts = operations.data?.counts ?? {
    approved: cases.filter((item) => item.status === "approved").length,
    documents: cases.reduce((total, item) => total + item.documents.length, 0) + standaloneDocuments.length,
    exceptions: cases.filter(
      (item) => item.risk_level === "high" || item.validation_findings.some((finding) => finding.severity === "error"),
    ).length,
    review_required: cases.filter((item) => item.status === "review_required").length,
    total_cases: cases.length,
  };
  const lanes = operations.data?.lanes?.length ? operations.data.lanes : fallbackLanes(cases);
  const totalQueue = lanes.reduce((total, lane) => total + lane.count, 0) || 1;
  const reviewReadyCases = cases
    .filter((item) => item.status === "review_required" || item.validation_findings.length > 0 || item.risk_level === "high")
    .slice(0, 5);
  const recentCases = (reviewReadyCases.length ? reviewReadyCases : cases).slice(0, 5);
  const blockingCases = cases.filter((item) => item.validation_findings.some((finding) => finding.severity === "error")).length;
  const pendingJobs = jobs.filter((job) => ["queued", "processing", "retry_scheduled"].includes(job.status)).length;
  const failedJobs = jobs.filter((job) => job.status === "failed").length;
  const platformComponents = platform.data?.components ?? [];
  const readyComponents = platformComponents.filter((item) =>
    ["ready", "configured", "passed", "clean"].includes(item.status.toLowerCase()),
  ).length;
  const platformReadiness = platformComponents.length ? readyComponents / platformComponents.length : 0;
  const fieldRows = Object.entries(accuracy.data?.field_accuracy ?? {}).slice(0, 5);
  const benchmarkF1 = accuracy.data?.benchmark?.overall.field_f1;
  const systemTemplates = templateStudio.data?.templates.filter((template) => template.locked || template.source === "system") ?? [];
  const customProfiles = templateStudio.data?.profiles ?? [];
  const approvedProfiles = customProfiles.filter((profile) => profile.status === "approved").length;
  const activeProviderCount =
    ocrPipeline.data?.providers.filter((provider) => ["ready", "configured", "active"].includes(provider.status.toLowerCase())).length ?? 0;
  const handoffCount = (integrationOps.data?.webhooks.length ?? 0) + (integrationOps.data?.sftp.status === "configured" ? 1 : 0);
  const bottlenecks = operations.data?.bottlenecks ?? [];
  const nextActions =
    operations.data?.next_best_actions?.length
      ? operations.data.next_best_actions
      : [
          "Clear blocking validation issues before export",
          "Prioritize high-risk or long-waiting review cases",
          "Configure missing verification adapters by institution",
        ];

  return (
    <div className="space-y-4">
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[var(--shadow-soft)]">
        <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill status={operations.status === "error" ? "warning" : "live"} label="Operations cockpit" />
              <StatusPill status={platform.data?.deployment_target ?? "private cloud"} label={labelize(platform.data?.country ?? "Nepal")} />
            </div>
            <h1 className="mt-3 max-w-4xl text-xl font-extrabold leading-tight text-slate-950 sm:text-2xl">
              Command center for Nepal KYC flow.
            </h1>
            <p className="mt-2 max-w-3xl text-xs leading-5 text-slate-600">
              Intake, extraction, review pressure, exception handling, permanent identity coverage, and downstream delivery are tracked as one
              operating spine.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <DashboardLink href="/cases" icon={<Boxes size={15} />} label="Applications" tone="primary" />
              <DashboardLink href="/documents" icon={<Upload size={15} />} label="Add Documents" />
              <DashboardLink href="/review" icon={<ClipboardCheck size={15} />} label="Review Queue" />
              <DashboardLink href="/templates" icon={<FileCog size={15} />} label="Formats" />
            </div>
          </div>
          <div className="grid min-w-0 gap-3 sm:grid-cols-3 lg:grid-cols-1">
            <ExecutiveReadout
              icon={<ShieldCheck size={18} />}
              label="Platform readiness"
              value={pct(platformReadiness)}
              detail={`${readyComponents}/${platformComponents.length || 0} controls ready`}
              tone={platformReadiness >= 0.8 ? "emerald" : "amber"}
            />
            <ExecutiveReadout
              icon={<Workflow size={18} />}
              label="Review pressure"
              value={`${counts.review_required}`}
              detail={`${blockingCases} blocking case(s)`}
              tone={counts.review_required || blockingCases ? "amber" : "emerald"}
            />
            <ExecutiveReadout
              icon={<Network size={18} />}
              label="Handoff channels"
              value={`${handoffCount}`}
              detail={`${exportProfiles.length} export profile(s)`}
              tone={handoffCount ? "emerald" : "amber"}
            />
          </div>
        </div>
      </section>

      <ResourceIssue resource={operations} label="Operations dashboard unavailable" />
      <ResourceIssue resource={platform} label="Platform readiness unavailable" />

      <section className="rounded-2xl border border-slate-200 bg-white p-3 shadow-[var(--shadow-soft)]">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 px-1">
          <div>
            <h2 className="text-sm font-extrabold text-slate-950">Operating Signals</h2>
            <p className="mt-1 text-xs font-semibold text-slate-500">Flow health from upload to approved handoff.</p>
          </div>
          <StatusBadge status={counts.exceptions ? "needs_review" : counts.review_required ? "queued" : "clean"} />
        </div>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-6">
          <MetricCard icon={<Boxes size={17} />} label="Applications" tone="cyan" value={`${counts.total_cases}`} detail="active files" />
          <MetricCard icon={<FileSearch size={17} />} label="Documents" tone="slate" value={`${counts.documents}`} detail="page evidence" />
          <MetricCard
            icon={<ClipboardCheck size={17} />}
            label="Review"
            tone={counts.review_required ? "amber" : "emerald"}
            value={`${counts.review_required}`}
            detail="awaiting decision"
          />
          <MetricCard
            icon={<AlertTriangle size={17} />}
            label="Exceptions"
            tone={counts.exceptions ? "rose" : "emerald"}
            value={`${counts.exceptions}`}
            detail="needs intervention"
          />
          <MetricCard icon={<BadgeCheck size={17} />} label="Approved" tone="emerald" value={`${counts.approved}`} detail="exportable records" />
          <MetricCard
            icon={<RefreshCcw size={17} />}
            label="Processing"
            tone={failedJobs ? "rose" : pendingJobs ? "amber" : "slate"}
            value={`${pendingJobs}`}
            detail={failedJobs ? `${failedJobs} failed` : "pending jobs"}
          />
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.08fr)_minmax(360px,0.92fr)]">
        <DashboardPanel icon={<GitBranch size={17} />} title="Workflow Board">
          <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-5">
            {lanes.map((lane) => {
              const tone = laneTone(lane.key);
              return (
                <Link
                  className={`group min-w-0 rounded-xl border p-3 ${toneClasses[tone]} hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)]`}
                  href={lane.key.includes("review") ? "/review" : lane.key.includes("export") ? "/integrations" : "/cases"}
                  key={lane.key}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-extrabold">{lane.label}</p>
                      <p className="mt-1 line-clamp-2 text-xs opacity-75">{lane.description}</p>
                    </div>
                    <span className="font-mono text-2xl font-extrabold">{lane.count}</span>
                  </div>
                  <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/75">
                    <div
                      className="h-full rounded-full bg-current opacity-70"
                      style={{ width: `${Math.max(6, Math.round((lane.count / totalQueue) * 100))}%` }}
                    />
                  </div>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {lane.case_ids.slice(0, 3).map((id) => (
                      <span className="rounded-full bg-white/75 px-2 py-1 font-mono text-[10px] font-bold" key={id}>
                        {compactId(id)}
                      </span>
                    ))}
                    {lane.case_ids.length > 3 ? (
                      <span className="rounded-full bg-white/75 px-2 py-1 text-[10px] font-bold">+{lane.case_ids.length - 3}</span>
                    ) : null}
                  </div>
                </Link>
              );
            })}
          </div>
        </DashboardPanel>

        <DashboardPanel icon={<AlertTriangle size={17} />} title="Bottlenecks And Next Actions">
          <div className="space-y-3">
            {(bottlenecks.length ? bottlenecks : [{ key: "clear", severity: "clean", message: "No active bottlenecks in this queue" }]).map(
              (item) => (
                <div className="grid grid-cols-[auto_1fr] gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-3" key={item.key}>
                  <span className={`mt-0.5 h-2.5 w-2.5 rounded-full ${dotTone(item.severity)}`} />
                  <div className="min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <p className="line-clamp-2 text-sm font-bold text-slate-950">{item.message}</p>
                      <StatusBadge status={item.severity} />
                    </div>
                  </div>
                </div>
              ),
            )}
            <div className="rounded-xl border border-slate-200 bg-white p-3">
              <p className="mb-2 text-xs font-extrabold uppercase tracking-[0.12em] text-slate-500">Next best actions</p>
              <div className="space-y-2">
                {nextActions.slice(0, 4).map((action) => (
                  <div className="flex gap-2 text-sm text-slate-700" key={action}>
                    <CheckCircle2 className="mt-0.5 shrink-0 text-emerald-600" size={15} />
                    <span className="line-clamp-2">{action}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </DashboardPanel>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <DashboardPanel icon={<Landmark size={17} />} title="Nepal Intelligence Fabric">
          <div className="grid gap-3 md:grid-cols-2">
            <CapabilityTile
              icon={<Fingerprint size={17} />}
              label="Permanent ID formats"
              value={`${systemTemplates.length}`}
              detail="Citizenship, National ID, passport, license"
              status={systemTemplates.length >= 4 ? "ready" : "needs_review"}
            />
            <CapabilityTile
              icon={<Route size={17} />}
              label="Location cross-check"
              value="Registry"
              detail="Province, district, municipality/VDC, ward"
              status="ready"
            />
            <CapabilityTile
              icon={<SearchCheck size={17} />}
              label="Name and address candidates"
              value="Reviewer-safe"
              detail="Lexicon and address evidence suggestions"
              status="active"
            />
            <CapabilityTile
              icon={<Layers3 size={17} />}
              label="Template profiles"
              value={`${approvedProfiles}/${customProfiles.length || 0}`}
              detail="Approved tenant formats"
              status={approvedProfiles ? "configured" : "not_configured"}
            />
          </div>
        </DashboardPanel>

        <DashboardPanel icon={<ClipboardCheck size={17} />} title="Priority Worklist">
            <div className="overflow-hidden rounded-xl border border-slate-200">
            <div className="grid grid-cols-[minmax(0,1.1fr)_120px_96px_96px] gap-3 border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs font-extrabold uppercase tracking-[0.1em] text-slate-500">
              <span>Applicant</span>
              <span>Status</span>
              <span>Docs</span>
              <span>Updated</span>
            </div>
            <div className="max-h-[310px] overflow-auto">
              {recentCases.length ? (
                recentCases.map((item) => (
                  <Link
                    className="grid grid-cols-[minmax(0,1.1fr)_120px_96px_96px] gap-3 border-b border-slate-100 px-3 py-2.5 text-xs last:border-b-0 hover:bg-cyan-50/60"
                    href="/cases"
                    key={item.id}
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-bold text-slate-950">{item.applicant_name}</span>
                      <span className="mt-1 block truncate font-mono text-xs text-slate-500">{item.integration_ref ?? compactId(item.id)}</span>
                    </span>
                    <span className="min-w-0">
                      <StatusBadge status={item.risk_level === "high" ? "high" : item.status} />
                    </span>
                    <span className="font-mono font-bold text-slate-700">{item.documents.length}</span>
                    <span className="truncate text-xs font-semibold text-slate-500">{formatDate(item.updated_at ?? item.created_at)}</span>
                  </Link>
                ))
              ) : (
                <p className="p-4 text-sm text-slate-500">No applications loaded yet.</p>
              )}
            </div>
          </div>
        </DashboardPanel>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <DashboardPanel icon={<Activity size={17} />} title="Accuracy Program">
          <div className="grid grid-cols-2 gap-2">
            <MiniReadout label="Benchmark F1" value={pct(benchmarkF1)} />
            <MiniReadout label="Corrections" value={`${accuracy.data?.correction_count ?? 0}`} />
          </div>
          <div className="mt-3 space-y-2">
            {fieldRows.length ? (
              fieldRows.map(([fieldKey, row]) => (
                <div className="grid grid-cols-[1fr_auto] gap-3 rounded-xl border border-slate-200 p-3 text-xs" key={fieldKey}>
                  <span className="min-w-0">
                    <span className="block truncate font-bold text-slate-950">{labelize(fieldKey)}</span>
                    <span className="mt-1 block truncate text-slate-500">
                      {row.observed} observed · {row.corrections} corrected
                    </span>
                  </span>
                  <span className="font-mono font-bold text-slate-800">{pct(row.estimated_accuracy)}</span>
                </div>
              ))
            ) : (
              <EmptyNote text="Reviewer corrections will populate field-level accuracy." />
            )}
          </div>
        </DashboardPanel>

        <DashboardPanel icon={<Gauge size={17} />} title="Recognition And Formats">
          <div className="grid grid-cols-2 gap-2">
            <MiniReadout label="Recognition" value={`${activeProviderCount}`} />
            <MiniReadout label="Templates" value={`${templateStudio.data?.templates.length ?? 0}`} />
          </div>
          <ResourceIssue resource={ocrPipeline} label="Recognition pipeline unavailable" />
          <div className="mt-3 space-y-2">
            {(ocrPipeline.data?.providers ?? []).slice(0, 3).map((provider) => (
              <div className="grid grid-cols-[1fr_auto] gap-3 rounded-xl border border-slate-200 p-3 text-xs" key={provider.key}>
                <span className="min-w-0">
                  <span className="block truncate font-bold text-slate-950">{providerLabel(provider)}</span>
                  <span className="mt-1 block truncate text-slate-500">{providerBestFor(provider)}</span>
                </span>
                <StatusBadge status={provider.status} />
              </div>
            ))}
          </div>
        </DashboardPanel>

        <DashboardPanel icon={<Database size={17} />} title="System Handoff">
          <ResourceIssue resource={integrationOps} label="Integration operations unavailable" />
          <div className="grid grid-cols-3 gap-2">
            <MiniReadout label="Hooks" value={`${integrationOps.data?.webhooks.length ?? 0}`} />
            <MiniReadout label="Retry" value={`${integrationOps.data?.retry_queue.length ?? 0}`} />
            <MiniReadout label="SFTP" value={`${integrationOps.data?.sftp.pending_batches ?? 0}`} />
          </div>
          <div className="mt-3 space-y-2">
            {(integrationOps.data?.webhooks ?? []).slice(0, 2).map((hook) => (
              <div className="grid grid-cols-[1fr_auto] gap-3 rounded-xl border border-slate-200 p-3 text-xs" key={hook.key}>
                <span className="min-w-0">
                  <span className="block truncate font-bold text-slate-950">{hook.key}</span>
                  <span className="mt-1 block truncate font-mono text-slate-500">{hook.url}</span>
                </span>
                <StatusBadge status={hook.status} />
              </div>
            ))}
            {integrationOps.data?.retry_queue.slice(0, 1).map((event) => (
              <div className="grid grid-cols-[1fr_auto] gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs" key={event.event_id}>
                <span className="min-w-0">
                  <span className="block truncate font-mono font-bold text-amber-950">{event.event_id}</span>
                  <span className="mt-1 block truncate text-amber-800">{event.last_error ?? event.mode}</span>
                </span>
                <StatusBadge status={event.status} />
              </div>
            ))}
            {!integrationOps.data?.webhooks.length && !integrationOps.data?.retry_queue.length ? (
              <EmptyNote text="Configure webhook or SFTP channels before production handoff." />
            ) : null}
          </div>
        </DashboardPanel>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <DashboardPanel icon={<LockKeyhole size={17} />} title="Platform Controls">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {platformComponents.slice(0, 6).map((component) => (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3" key={component.key}>
                <div className="flex items-start justify-between gap-2">
                  <p className="min-w-0 truncate text-sm font-bold text-slate-950">{component.label}</p>
                  <StatusBadge status={component.status} />
                </div>
                <p className="mt-2 line-clamp-2 text-xs text-slate-600">{component.detail}</p>
                <p className="mt-2 line-clamp-2 text-xs font-semibold text-slate-500">{component.next_step}</p>
              </div>
            ))}
            {!platformComponents.length ? <EmptyNote text="Platform readiness will appear when the backend responds." /> : null}
          </div>
        </DashboardPanel>

        <DashboardPanel icon={<FileSearch size={17} />} title="Selected File Snapshot">
          {selectedCase ? (
            <div className="space-y-3">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                <p className="truncate text-base font-extrabold text-slate-950">{selectedCase.applicant_name}</p>
                <p className="mt-1 truncate font-mono text-xs text-slate-500">{selectedCase.integration_ref ?? compactId(selectedCase.id)}</p>
                <div className="mt-3 grid grid-cols-3 gap-2">
                  <MiniReadout label="Docs" value={`${selectedCase.documents.length}`} />
                  <MiniReadout label="Fields" value={`${selectedCase.extracted_fields.length}`} />
                  <MiniReadout label="Issues" value={`${selectedCase.validation_findings.length}`} />
                </div>
              </div>
              <DashboardLink href="/cases" icon={<ArrowRight size={15} />} label="Open Workbench" tone="primary" />
            </div>
          ) : (
            <div className="space-y-3">
              <EmptyNote text="Create an application or upload standalone documents to begin." />
              <DashboardLink href="/documents" icon={<Upload size={15} />} label="Upload Documents" tone="primary" />
            </div>
          )}
        </DashboardPanel>
      </section>
    </div>
  );
}

function DashboardPanel({ children, icon, title }: { children: ReactNode; icon: ReactNode; title: string }) {
  return (
    <section className="min-w-0 rounded-2xl border border-slate-200 bg-white p-3 shadow-[var(--shadow-soft)]">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="truncate text-sm font-extrabold text-slate-950">{title}</h2>
        <span className="rounded-lg bg-cyan-50 p-1.5 text-cyan-700">{icon}</span>
      </div>
      {children}
    </section>
  );
}

function MetricCard({
  detail,
  icon,
  label,
  tone,
  value,
}: {
  detail: string;
  icon: ReactNode;
  label: string;
  tone: MetricTone;
  value: string;
}) {
  return (
    <div className="group min-w-0 overflow-hidden rounded-xl border border-slate-200 bg-slate-50 shadow-sm transition hover:-translate-y-0.5 hover:border-cyan-200 hover:bg-white">
      <div className={`h-1 ${railTone(tone)}`} />
      <div className="p-2.5">
        <div className="flex items-center justify-between gap-2">
          <p className="truncate text-[10px] font-extrabold uppercase tracking-[0.1em] text-slate-500">{label}</p>
          <span className={`rounded-lg p-1.5 ${iconToneClasses[tone]}`}>{icon}</span>
        </div>
        <div className="mt-2 flex items-end justify-between gap-2">
          <p className="truncate font-mono text-xl font-extrabold text-slate-950">{value}</p>
          <p className="min-w-0 truncate text-right text-[11px] font-bold text-slate-500">{detail}</p>
        </div>
      </div>
    </div>
  );
}

function ExecutiveReadout({
  detail,
  icon,
  label,
  tone,
  value,
}: {
  detail: string;
  icon: ReactNode;
  label: string;
  tone: MetricTone;
  value: string;
}) {
  return (
    <div className={`min-w-0 rounded-xl border p-3 ${toneClasses[tone]}`}>
      <div className="flex items-start justify-between gap-2">
        <span className="min-w-0">
          <span className="block truncate text-[10px] font-extrabold uppercase tracking-[0.1em] opacity-75">{label}</span>
          <span className="mt-1.5 block truncate font-mono text-xl font-extrabold">{value}</span>
          <span className="mt-1 block truncate text-xs font-bold opacity-70">{detail}</span>
        </span>
        <span className={`rounded-lg p-1.5 ${iconToneClasses[tone]}`}>{icon}</span>
      </div>
    </div>
  );
}

function CapabilityTile({
  detail,
  icon,
  label,
  status,
  value,
}: {
  detail: string;
  icon: ReactNode;
  label: string;
  status: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-start justify-between gap-2">
        <span className="min-w-0">
          <span className="block truncate text-xs font-extrabold text-slate-950">{label}</span>
          <span className="mt-1 block truncate text-xs text-slate-500">{detail}</span>
        </span>
        <span className="rounded-lg bg-white p-1.5 text-cyan-700 shadow-sm">{icon}</span>
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="truncate font-mono text-xs font-extrabold text-slate-800">{value}</span>
        <StatusBadge status={status} />
      </div>
    </div>
  );
}

function MiniReadout({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-slate-200 bg-slate-50 p-2.5">
      <p className="truncate text-[10px] font-extrabold uppercase tracking-[0.1em] text-slate-500">{label}</p>
      <p className="mt-1 truncate font-mono text-sm font-extrabold text-slate-950">{value}</p>
    </div>
  );
}

function StatusBadge({ status }: { status?: string }) {
  return (
    <span className={`inline-flex max-w-full items-center rounded-md border px-2 py-0.5 text-[11px] font-bold ${statusTone(status)}`}>
      <span className="truncate">{labelize(status)}</span>
    </span>
  );
}

function StatusPill({ label, status }: { label: string; status: string }) {
  return (
    <span className={`inline-flex h-7 max-w-full items-center gap-1.5 rounded-full border px-2.5 text-[11px] font-extrabold ${statusTone(status)}`}>
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dotTone(status)}`} />
      <span className="truncate">{label}</span>
    </span>
  );
}

function DashboardLink({
  href,
  icon,
  label,
  tone = "secondary",
}: {
  href: string;
  icon: ReactNode;
  label: string;
  tone?: "primary" | "secondary";
}) {
  const className =
    tone === "primary"
      ? "border-cyan-600 bg-gradient-to-r from-cyan-600 to-teal-500 text-white shadow-[var(--shadow-button)] hover:shadow-[var(--shadow-lift)]"
      : "border-slate-200 bg-white text-slate-700 hover:border-cyan-200 hover:bg-cyan-50 hover:text-cyan-700 hover:shadow-[var(--shadow-soft)]";
  return (
    <Link
      className={`inline-flex h-9 max-w-full items-center justify-center gap-1.5 rounded-full border px-3 text-xs font-extrabold hover:-translate-y-0.5 ${className}`}
      href={href}
    >
      <span className="shrink-0">{icon}</span>
      <span className="truncate">{label}</span>
    </Link>
  );
}

function ResourceIssue<T>({ label, resource }: { label: string; resource: ResourceState<T> }) {
  if (resource.status !== "error") {
    return null;
  }
  return (
    <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs font-semibold text-amber-900">
      <AlertTriangle className="mt-0.5 shrink-0" size={16} />
      <p className="min-w-0 break-words">{resource.error || label}</p>
    </div>
  );
}

function EmptyNote({ text }: { text: string }) {
  return <p className="rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-xs text-slate-500">{text}</p>;
}

function dotTone(status?: string) {
  const value = (status ?? "").toLowerCase();
  if (["clean", "live", "ready", "configured", "passed", "approved", "verified"].includes(value)) {
    return "bg-emerald-500";
  }
  if (["warning", "partial", "queued", "review_required", "not_configured", "needs_review"].includes(value)) {
    return "bg-amber-500";
  }
  if (["error", "failed", "blocked", "high", "rejected"].includes(value)) {
    return "bg-rose-500";
  }
  return "bg-cyan-500";
}

function railTone(tone: MetricTone) {
  if (tone === "emerald") {
    return "bg-emerald-500";
  }
  if (tone === "amber") {
    return "bg-amber-500";
  }
  if (tone === "rose") {
    return "bg-rose-500";
  }
  if (tone === "slate") {
    return "bg-slate-300";
  }
  return "bg-cyan-500";
}
