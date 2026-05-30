"use client";

import { FormEvent, useState } from "react";
import { LockKeyhole, ShieldCheck } from "lucide-react";

import { LipiOcrLogo } from "../brand/lipiocr-logo";
import type { OperatorPrincipal, OperatorSessionRequest } from "../../lib/auth-client";

const roles = ["maker", "checker", "auditor", "admin"];

export function LoginPanel({
  session,
  signingIn,
  onSignIn,
  onSignOut,
}: {
  session: OperatorPrincipal | null;
  signingIn: boolean;
  onSignIn: (payload: OperatorSessionRequest) => Promise<void>;
  onSignOut: () => Promise<void>;
}) {
  const [username, setUsername] = useState("maker.one");
  const [tenantId, setTenantId] = useState("demo-institution");
  const [branchCode, setBranchCode] = useState("KTM-01");
  const [role, setRole] = useState("maker");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSignIn({
      username,
      tenant_id: tenantId,
      branch_code: branchCode,
      role,
    });
  }

  if (session) {
    return (
      <section className="border-b border-emerald-200 bg-emerald-50/80">
        <div className="mx-auto flex max-w-[1800px] flex-col gap-3 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <span className="mt-0.5 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white shadow-[var(--shadow-soft)]">
              <LipiOcrLogo showWordmark={false} size="sm" />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-extrabold text-slate-950">Operator session active</p>
              <p className="mt-1 text-sm font-semibold text-slate-600">
                {session.user_id} · {session.tenant_id}
                {session.branch_code ? ` · ${session.branch_code}` : ""} · {session.role}
              </p>
            </div>
          </div>
          <button
            className="inline-flex h-10 items-center justify-center rounded-lg border border-emerald-200 bg-white px-4 text-sm font-bold text-emerald-800 transition hover:border-emerald-300 hover:bg-emerald-100"
            onClick={onSignOut}
            type="button"
          >
            Sign out
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="border-b border-amber-200 bg-amber-50/80">
      <form
        className="mx-auto grid max-w-[1800px] gap-3 px-4 py-4 sm:px-6 xl:grid-cols-[minmax(260px,1fr)_minmax(620px,auto)] xl:items-center"
        onSubmit={handleSubmit}
      >
        <div className="flex min-w-0 items-start gap-3">
          <span className="mt-0.5 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white text-amber-700 shadow-[var(--shadow-soft)]">
            <LockKeyhole size={18} />
          </span>
          <div className="min-w-0">
            <p className="text-sm font-extrabold text-slate-950">Operator session required</p>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
              Sign in with tenant, branch, and role context before processing customer documents.
            </p>
          </div>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-[160px_180px_130px_260px_110px] xl:items-center">
          <input
            className="h-11 min-w-0 rounded-lg border border-amber-200 bg-white px-3 text-sm font-semibold text-slate-900 shadow-sm outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
            onChange={(event) => setUsername(event.target.value)}
            placeholder="User"
            value={username}
          />
          <input
            className="h-11 min-w-0 rounded-lg border border-amber-200 bg-white px-3 text-sm font-semibold text-slate-900 shadow-sm outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
            onChange={(event) => setTenantId(event.target.value)}
            placeholder="Tenant"
            value={tenantId}
          />
          <input
            className="h-11 min-w-0 rounded-lg border border-amber-200 bg-white px-3 text-sm font-semibold text-slate-900 shadow-sm outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
            onChange={(event) => setBranchCode(event.target.value)}
            placeholder="Branch"
            value={branchCode}
          />
          <div className="grid h-11 grid-cols-4 rounded-lg border border-amber-200 bg-white p-1 shadow-sm">
            {roles.map((item) => (
              <button
                className={`rounded-md px-2 text-xs font-extrabold capitalize transition ${
                  role === item ? "bg-cyan-600 text-white shadow-sm" : "text-slate-600 hover:bg-slate-100"
                }`}
                key={item}
                onClick={() => setRole(item)}
                type="button"
              >
                {item}
              </button>
            ))}
          </div>
          <button
            className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-cyan-600 to-teal-500 px-4 text-sm font-bold text-white shadow-[var(--shadow-button)] transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={signingIn}
            type="submit"
          >
            <ShieldCheck size={16} />
            {signingIn ? "Signing in" : "Sign in"}
          </button>
        </div>
      </form>
    </section>
  );
}
