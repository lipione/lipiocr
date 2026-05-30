import type { ReactNode } from "react";

type TenantSummary = {
  tenant_id: string;
  name: string;
  status: string;
  users: { user_id: string; role: string; branch_code?: string | null; status: string }[];
  settings: {
    retention_days: number;
    allowed_export_profiles: string[];
    data_region: string;
  };
};

function Cell({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <p className="text-xs font-bold uppercase text-slate-500">{label}</p>
      <div className="mt-2 text-sm font-semibold text-slate-900">{children}</div>
    </div>
  );
}

export function TenantAdmin({ tenants }: { tenants: TenantSummary[] }) {
  return (
    <div className="grid gap-3">
      {tenants.map((tenant) => (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4" key={tenant.tenant_id}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-base font-extrabold text-slate-950">{tenant.name}</p>
              <p className="mt-1 font-mono text-xs text-slate-500">{tenant.tenant_id}</p>
            </div>
            <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700">
              {tenant.status}
            </span>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <Cell label="Users">{tenant.users.length}</Cell>
            <Cell label="Retention">{tenant.settings.retention_days} days</Cell>
            <Cell label="Exports">{tenant.settings.allowed_export_profiles.join(", ")}</Cell>
          </div>
        </div>
      ))}
    </div>
  );
}
