# LipiOCR Frontend

This is the Next.js workspace for LipiOCR Enterprise. It provides the product home, case/document workbench, review workflow, verification hub, template studio, integrations center, analytics, and admin surfaces.

## Stack

- Next.js 16 App Router.
- React 19.
- TypeScript.
- Tailwind CSS 4.
- `lucide-react` for icons.
- Project API client in `src/lib/api-client.ts`.

Read `AGENTS.md` before changing Next.js conventions. This project uses a newer Next.js version with behavior that may differ from older examples.

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Product intro and feature overview. |
| `/dashboard` | Operations command center. |
| `/cases` | Case intake, selected case workflow, review, export, audit context. |
| `/documents` | Standalone and linked document processing. |
| `/review` | Maker-checker workbench. |
| `/verification` | Verification adapters and case checks. |
| `/templates` | Template studio and extraction governance. |
| `/integrations` | CBS/LOS/CRM/DMS export profiles, webhook/SFTP operations. |
| `/analytics` | Accuracy, corrections, benchmark posture. |
| `/admin` | Platform, tenant, RBAC, audit, and compliance posture. |

## Local Development

From the repository root:

```bash
make frontend-install
make frontend-dev
```

Or from this directory:

```bash
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8010 npm run dev
```

Open `http://localhost:3000`.

## Environment

Local `.env.local` example:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8010
NEXT_PUBLIC_BASE_PATH=
NEXT_PUBLIC_API_PORT=8010
```

For subpath hosting such as `https://ai.silverlining.com.np/lipiocr`:

```bash
NEXT_PUBLIC_BASE_PATH=/lipiocr
NEXT_PUBLIC_API_BASE_URL=auto
```

The API client supports:

- Explicit API base URL.
- Same-host reverse proxy mode through `auto`.
- Base-path deployments.
- Cookie credentials for session auth.
- Friendly formatting for missing/invalid API key responses.

## Verification

```bash
npm run test
npm run lint
npm run build
```

Root Make targets:

```bash
make frontend-test
make frontend-build
make test
```

## UI Guidelines

- Keep workflow screens task-focused and dense enough for repeated operations.
- Avoid hiding core review actions behind dropdowns.
- Keep split-view document evidence and editable extracted data close together.
- Preserve original OCR values, corrected values, confidence, and audit reasons in UI surfaces.
- Use existing workspace components and route patterns before creating new layout primitives.
- Use icons for compact actions where they are familiar, with accessible labels/tooltips.
- Keep model/provider names out of operator-facing UI; use product language such as LipiCore.

## Common Files

| File | Purpose |
| --- | --- |
| `src/app/layout.tsx` | Global app shell. |
| `src/app/page.tsx` | Product home. |
| `src/components/enterprise-workspace.tsx` | Main route-backed workspace component. |
| `src/components/product-home.tsx` | Product intro page. |
| `src/components/templates/template-studio.tsx` | Template editor/workflow. |
| `src/lib/api-client.ts` | API base URL resolution, fetch wrapper, credentials. |
| `src/lib/auth-client.ts` | Session/auth helpers. |
| `src/types/workspace.ts` | Shared frontend types for workspace payloads. |

## Troubleshooting

`Failed to fetch`

- Confirm backend is running at `http://localhost:8010`.
- Confirm `NEXT_PUBLIC_API_BASE_URL` is set.
- Confirm backend `LIPIOCR_CORS_ORIGINS` includes the frontend origin.

`401 Missing API key`

- Backend auth is enabled.
- Login through the UI/session endpoint or configure a valid API key.
- For local workflow-only development, run backend with `LIPIOCR_API_AUTH_ENABLED=false`.

Build fails after changing API data shapes

- Update `src/types/workspace.ts`.
- Update any route/component that consumes the payload.
- Add/update tests in `frontend/scripts/*.test.mjs` when helper behavior changes.
