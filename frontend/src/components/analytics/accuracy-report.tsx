import type { AccuracyAnalytics } from "../../types/workspace";

function pct(value: number | undefined) {
  return `${Math.round((value ?? 0) * 100)}%`;
}

type BenchmarkReport = {
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
              <span className="font-mono font-bold text-indigo-700">{pct(row.field_f1)}</span>
            </div>
            <p className="mt-1 text-xs text-slate-500">Reviewer correction rate {row.reviewer_correction_rate}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
