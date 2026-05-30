import type { ReactNode } from "react";

import type { AccuracyAnalytics } from "../../types/workspace";

function pct(value: number | undefined) {
  return `${Math.round((value ?? 0) * 100)}%`;
}

type BenchmarkReport = {
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

export function AccuracyReport({ accuracy }: { accuracy?: AccuracyAnalytics | null }) {
  const benchmark = accuracy?.benchmark as BenchmarkReport | undefined;
  if (!benchmark) {
    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
        Accuracy benchmark data has not been generated yet.
      </div>
    );
  }
  const weakestFields = benchmark.weak_fields ?? [];
  const fieldRows = Object.entries(benchmark.by_field ?? {})
    .sort(([, left], [, right]) => left.f1 - right.f1 || right.expected - left.expected)
    .slice(0, 6);
  const documentRows = Object.entries(benchmark.by_document_type ?? {}).slice(0, 5);
  const languageRows = Object.entries(benchmark.by_language ?? {});
  const bucketRows = Object.entries(benchmark.confidence_buckets ?? {});
  const readiness = benchmark.dataset_readiness;

  return (
    <div className="grid gap-3">
      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs font-bold uppercase text-slate-500">Samples</p>
          <p className="mt-2 text-2xl font-extrabold text-slate-950">{benchmark.sample_count}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs font-bold uppercase text-slate-500">Field F1</p>
          <p className="mt-2 text-2xl font-extrabold text-slate-950">{pct(benchmark.overall.field_f1)}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs font-bold uppercase text-slate-500">Correction Rate</p>
          <p className="mt-2 text-2xl font-extrabold text-slate-950">{benchmark.overall.reviewer_correction_rate}</p>
        </div>
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        {Object.entries(benchmark.by_mode).map(([mode, row]) => (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm" key={mode}>
            <div className="flex items-center justify-between gap-3">
              <span className="font-bold capitalize text-slate-900">{mode}</span>
              <span className="font-mono font-bold text-cyan-700">{pct(row.field_f1)}</span>
            </div>
            <p className="mt-1 text-xs text-slate-500">Reviewer correction rate {row.reviewer_correction_rate}</p>
          </div>
        ))}
      </div>
      <div className="grid gap-2 md:grid-cols-3">
        <MetricTile label="Document Types" value={`${readiness?.document_type_count ?? documentRows.length}`} />
        <MetricTile label="Handwriting Samples" value={`${benchmark.handwriting?.sample_count ?? 0}`} />
        <MetricTile label="Nepali Handwriting Fields" value={`${benchmark.handwriting?.nepali_field_count ?? 0}`} />
      </div>
      {languageRows.length || bucketRows.length ? (
        <div className="grid gap-2 lg:grid-cols-2">
          <Breakdown title="Language Accuracy">
            {languageRows.map(([language, row]) => (
              <ScoreRow
                detail={`${row.field_count} fields · correction rate ${row.reviewer_correction_rate}`}
                key={language}
                label={labelize(language)}
                value={pct(row.field_f1)}
              />
            ))}
          </Breakdown>
          <Breakdown title="Confidence Calibration">
            {bucketRows.map(([bucket, row]) => (
              <ScoreRow
                detail={`${row.matched}/${row.field_count} matched`}
                key={bucket}
                label={labelize(bucket)}
                value={pct(row.precision)}
              />
            ))}
          </Breakdown>
        </div>
      ) : null}
      {fieldRows.length ? (
        <Breakdown title="Weakest Fields">
          {fieldRows.map(([fieldKey, row]) => (
            <ScoreRow
              detail={`${row.expected} expected · CER ${pct(row.average_character_error_rate)} · ${row.languages.join(", ") || "mixed"}`}
              key={fieldKey}
              label={labelize(fieldKey)}
              value={pct(row.f1)}
            />
          ))}
        </Breakdown>
      ) : null}
      {weakestFields.length ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
          <p className="font-extrabold">Benchmark attention</p>
          <p className="mt-1">
            Lowest confidence field: <span className="font-mono font-bold">{weakestFields[0].field_key}</span>. Use reviewer
            corrections and more approved samples before raising automation thresholds.
          </p>
        </div>
      ) : null}
      {readiness?.gaps?.length ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
          <p className="font-extrabold text-slate-900">Dataset gaps</p>
          {readiness.gaps.slice(0, 3).map((gap) => (
            <p className="mt-1" key={gap}>
              {gap}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <p className="text-xs font-bold uppercase text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-extrabold text-slate-950">{value}</p>
    </div>
  );
}

function Breakdown({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <p className="text-xs font-bold uppercase text-slate-500">{title}</p>
      <div className="mt-2 grid gap-2">{children}</div>
    </div>
  );
}

function ScoreRow({ detail, label, value }: { detail: string; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 text-sm">
      <span className="min-w-0">
        <span className="block truncate font-bold text-slate-900">{label}</span>
        <span className="block truncate text-xs text-slate-500">{detail}</span>
      </span>
      <span className="font-mono font-bold text-cyan-700">{value}</span>
    </div>
  );
}

function labelize(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}
