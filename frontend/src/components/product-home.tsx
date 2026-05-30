"use client";

import Image from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  BadgeCheck,
  BrainCircuit,
  Building2,
  ClipboardCheck,
  DatabaseZap,
  FileSearch,
  Languages,
  LockKeyhole,
  Network,
  RefreshCcw,
  ShieldCheck,
  Upload,
  Workflow,
} from "lucide-react";

const features = [
  {
    title: "Full-page document understanding",
    description:
      "Upload citizenship cards, passports, ASBA forms, licenses, bank forms, and unknown documents for OCR, handwriting capture, field detection, and reviewer-ready evidence.",
    icon: <FileSearch size={20} />,
  },
  {
    title: "Human review workflow",
    description:
      "Route low-confidence fields to operators, keep corrections editable, and preserve audit history before data reaches core banking or onboarding systems.",
    icon: <ClipboardCheck size={20} />,
  },
  {
    title: "Bilingual extraction",
    description:
      "Connect Nepali and English versions of the same customer information, reconcile confidence gaps, and prepare clean bilingual payloads.",
    icon: <Languages size={20} />,
  },
  {
    title: "Integration-ready exports",
    description:
      "Convert reviewed documents into structured JSON for KYC, onboarding, loan, archive, and downstream operations without forcing institutions to replace existing systems.",
    icon: <Network size={20} />,
  },
];

const workflow = [
  { label: "Upload", detail: "Single or multiple documents", icon: <Upload size={18} /> },
  { label: "Understand", detail: "LipiCore reads layout and fields", icon: <BrainCircuit size={18} /> },
  { label: "Review", detail: "Operators correct uncertain values", icon: <ClipboardCheck size={18} /> },
  { label: "Export", detail: "Approved data moves to existing systems", icon: <DatabaseZap size={18} /> },
];

const intelligenceCapabilities = [
  {
    title: "Bilingual field pairing",
    detail: "Creates name_ne/name_en, father_name_ne/father_name_en, and address_ne/address_en pairs while preserving the original OCR values.",
  },
  {
    title: "Auto translation and transliteration",
    detail: "Normalizes Nepali and English values into reviewer-safe forms for matching, export preparation, and correction suggestions.",
  },
  {
    title: "Cross-document entity reconciliation",
    detail: "Compares names across citizenship, bank forms, ASBA, passport, and license documents, including spelling and middle-initial variants.",
  },
  {
    title: "Confidence repair with audit reasons",
    detail: "Raises weak field confidence only when a stronger related field supports it, storing source field, corrected value, confidence, and audit reason.",
  },
];

const trustItems = [
  "On-premise or private cloud friendly",
  "Audit trail for every review action",
  "Maker-checker controls for financial operations",
  "Designed around Nepal KYC and document formats",
];

export function ProductHome() {
  return (
    <main className="min-h-screen bg-slate-50 text-slate-950">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur-xl">
        <nav className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <Link className="inline-flex items-center gap-3 font-extrabold text-slate-950" href="/">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-[var(--shadow-button)]">
              <ShieldCheck size={20} />
            </span>
            <span>LipiOCR Enterprise</span>
          </Link>
          <div className="hidden items-center gap-6 text-sm font-bold text-slate-600 md:flex">
            <a className="hover:text-indigo-700" href="#features">
              Features
            </a>
            <a className="hover:text-indigo-700" href="#workflow">
              Workflow
            </a>
            <a className="hover:text-indigo-700" href="#trust">
              Security
            </a>
          </div>
          <Link
            className="inline-flex h-10 items-center gap-2 rounded-full bg-gradient-to-r from-indigo-600 to-violet-600 px-4 text-sm font-bold text-white shadow-[var(--shadow-button)] hover:-translate-y-0.5"
            href="/dashboard"
          >
            Open Platform
            <ArrowRight size={16} />
          </Link>
        </nav>
      </header>

      <section className="relative isolate min-h-[500px] overflow-hidden border-b border-slate-200 bg-slate-950 sm:min-h-[540px] lg:min-h-[580px]">
        <Image
          alt="LipiOCR document review workspace with split preview and extracted fields"
          className="absolute inset-0 -z-10 h-full w-full object-cover opacity-58"
          fill
          priority
          sizes="100vw"
          src="/product-documents-workbench.png"
        />
        <div className="absolute inset-0 -z-10 bg-gradient-to-r from-slate-950 via-slate-950/78 to-slate-950/28" />
        <div className="mx-auto flex min-h-[500px] max-w-7xl flex-col justify-center px-4 py-14 sm:min-h-[540px] sm:px-6 lg:min-h-[580px] lg:py-16">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1.5 text-xs font-bold uppercase text-indigo-100 backdrop-blur">
              <Building2 size={14} />
              Nepal financial institutions
            </div>
            <h1 className="mt-6 max-w-3xl text-4xl font-extrabold leading-[1.1] text-white sm:text-5xl lg:text-6xl">
              LipiOCR Enterprise
            </h1>
            <p className="mt-5 max-w-2xl text-lg font-semibold leading-8 text-indigo-50 sm:text-xl">
              Document intelligence for KYC, onboarding, and operations.
            </p>
            <p className="mt-4 max-w-2xl text-base leading-7 text-slate-200">
              Read Nepali and English financial documents, extract structured fields, reconcile bilingual data, and let
              reviewers approve uncertain information before it enters institutional systems.
            </p>
            <div className="mt-5 inline-flex max-w-2xl items-center gap-2 rounded-xl border border-white/15 bg-white/10 px-4 py-3 text-sm font-bold leading-6 text-white backdrop-blur">
              <BrainCircuit className="shrink-0 text-indigo-200" size={18} />
              <span>LipiCore does OCR + bilingual normalization + entity reconciliation + reviewer-safe correction</span>
            </div>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                className="inline-flex h-12 items-center gap-2 rounded-full bg-white px-5 text-sm font-extrabold text-slate-950 shadow-[0_18px_40px_-18px_rgba(255,255,255,0.7)] hover:-translate-y-0.5"
                href="/documents"
              >
                Review Documents
                <ArrowRight size={17} />
              </Link>
              <Link
                className="inline-flex h-12 items-center gap-2 rounded-full border border-white/20 bg-white/10 px-5 text-sm font-extrabold text-white backdrop-blur hover:-translate-y-0.5 hover:bg-white/15"
                href="/cases"
              >
                Start KYC File
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section id="features" className="border-b border-slate-200 bg-white py-16 sm:py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <div className="max-w-2xl">
            <p className="text-sm font-bold uppercase text-indigo-600">Platform Capabilities</p>
            <h2 className="mt-3 text-3xl font-extrabold text-slate-950 sm:text-4xl">
              Built for real financial document operations.
            </h2>
          </div>
          <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {features.map((feature) => (
              <article
                className="rounded-xl border border-slate-100 bg-white p-5 shadow-[var(--shadow-soft)] hover:-translate-y-1 hover:shadow-[var(--shadow-lift)]"
                key={feature.title}
              >
                <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                  {feature.icon}
                </div>
                <h3 className="mt-5 text-lg font-extrabold text-slate-950">{feature.title}</h3>
                <p className="mt-3 text-sm leading-6 text-slate-600">{feature.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="border-b border-slate-200 bg-slate-950 py-16 text-white sm:py-20">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 sm:px-6 lg:grid-cols-[0.78fr_1.22fr] lg:items-start">
          <div>
            <p className="text-sm font-bold uppercase text-indigo-200">LipiCore Intelligence Layer</p>
            <h2 className="mt-3 text-3xl font-extrabold sm:text-4xl">
              OCR is only the first step.
            </h2>
            <p className="mt-4 text-base leading-7 text-slate-300">
              LipiCore keeps originals, creates normalized values, compares related fields, and records why a suggested
              correction is safe enough for reviewer attention.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {intelligenceCapabilities.map((item) => (
              <article className="rounded-xl border border-white/10 bg-white/[0.08] p-4 backdrop-blur" key={item.title}>
                <h3 className="text-base font-extrabold text-white">{item.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-300">{item.detail}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="workflow" className="border-b border-slate-200 bg-slate-50 py-16 sm:py-20">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 sm:px-6 lg:grid-cols-[0.85fr_1.15fr] lg:items-center">
          <div>
            <p className="text-sm font-bold uppercase text-indigo-600">Workflow</p>
            <h2 className="mt-3 text-3xl font-extrabold text-slate-950 sm:text-4xl">
              From uploaded file to verified data.
            </h2>
            <p className="mt-4 text-base leading-7 text-slate-600">
              LipiOCR does not pretend every document can be fully automated. It prioritizes field confidence,
              correction, audit, and integration so institutions can move faster without losing control.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {workflow.map((step, index) => (
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-[var(--shadow-soft)]" key={step.label}>
                <div className="flex items-center justify-between gap-3">
                  <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                    {step.icon}
                  </span>
                  <span className="font-mono text-xs font-bold text-slate-400">0{index + 1}</span>
                </div>
                <h3 className="mt-4 text-base font-extrabold text-slate-950">{step.label}</h3>
                <p className="mt-1 text-sm text-slate-600">{step.detail}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="trust" className="bg-white py-16 sm:py-20">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 sm:px-6 lg:grid-cols-[1fr_1fr] lg:items-start">
          <div>
            <p className="text-sm font-bold uppercase text-indigo-600">Enterprise Trust</p>
            <h2 className="mt-3 text-3xl font-extrabold text-slate-950 sm:text-4xl">
              Designed to integrate with existing institution systems.
            </h2>
            <p className="mt-4 text-base leading-7 text-slate-600">
              Keep the bank, microfinance, brokerage, insurance, or cooperative workflow intact. LipiOCR adds a review
              and intelligence layer that exports approved data through APIs, JSON, webhooks, or batch handoff.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                className="inline-flex h-11 items-center gap-2 rounded-full bg-gradient-to-r from-indigo-600 to-violet-600 px-5 text-sm font-bold text-white shadow-[var(--shadow-button)] hover:-translate-y-0.5"
                href="/integrations"
              >
                View Integrations
                <Workflow size={16} />
              </Link>
              <Link
                className="inline-flex h-11 items-center gap-2 rounded-full border border-slate-200 bg-white px-5 text-sm font-bold text-slate-700 shadow-[var(--shadow-soft)] hover:-translate-y-0.5 hover:border-indigo-200 hover:text-indigo-700"
                href="/verification"
              >
                View Verification
                <RefreshCcw size={16} />
              </Link>
            </div>
          </div>
          <div className="grid gap-3">
            {trustItems.map((item) => (
              <div className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4" key={item}>
                <span className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
                  <BadgeCheck size={16} />
                </span>
                <p className="text-sm font-bold leading-6 text-slate-800">{item}</p>
              </div>
            ))}
            <div className="rounded-xl border border-indigo-100 bg-indigo-50 p-5">
              <div className="flex items-center gap-3">
                <LockKeyhole className="text-indigo-600" size={20} />
                <h3 className="text-base font-extrabold text-slate-950">Private deployment ready</h3>
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-600">
                Supports institution-controlled infrastructure first, with clear review boundaries before production
                integrations are enabled.
              </p>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
