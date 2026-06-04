# LipiOCR Interface System

This file is the persistent interface memory for LipiOCR. It follows the project-memory pattern from `Dammyjay93/interface-design`: record the product direction, visual rules, component patterns, and decisions so future UI work stays consistent across sessions.

## Direction

**Personality:** Sophistication and Trust with operational density.

**Product posture:** LipiOCR is an enterprise document intelligence platform for Nepal financial institutions. The UI must feel like a bank-grade operations system, not a generic OCR demo, marketing dashboard, or decorative SaaS shell.

**Core workflow:** Intake -> extraction -> review -> approval -> export -> audit -> improvement.

**Workspace layers:**

- Operations: command center, applications, review queue, batches/uploads, exports.
- Intelligence: template studio, field normalization, address intelligence, name lexicon, validation rules, benchmark accuracy, correction learning.
- Governance: tenants, users/RBAC, permanent Nepal identity templates, audit logs, data lineage, security, integrations, incident/backup/DR readiness.

## Tokens

### Color

- Background: `#F8FAFC` and white surfaces.
- Text main: slate 950.
- Text muted: slate 500/600.
- Primary brand: teal/cyan with deep navy text.
- Action blue/cyan: navigation, active states, links.
- Emerald: approved, exported, healthy.
- Amber: warning, needs review, medium confidence.
- Rose: validation failure, SLA risk, compliance issue.
- Purple: draft, reviewer intervention, human decision states.

Do not let the interface become a one-color cyan/teal theme. Use color as status and information structure.

### Typography

- Use the existing geometric enterprise font direction.
- Dashboard and workbench headings should be concise and operational.
- Avoid hero-scale typography inside dense work surfaces.
- Monospace is reserved for IDs, integration references, API keys, and technical receipts.

### Spacing And Radius

- Base spacing: 4px/8px grid.
- Work surfaces: compact but breathable.
- Cards/panels: 16px to 20px padding.
- Radius: 12px to 22px for workspace panels, 8px to 12px for fields and controls.
- Do not nest cards inside cards unless the inner item is a repeated row, field, or status object.

### Depth

- Use thin borders and soft colored shadows.
- Shadow is for major workspace panels only.
- Tables, field rows, and evidence rows should rely mostly on borders and background states.

## Navigation Rules

- The primary dashboard is the Command Center, not a generic "Dashboard."
- Use the enterprise shell pattern from the approved mockups: persistent left navigation, compact top utility bar, route-specific content header, and page-specific work surface.
- Do not hide primary actions behind dropdowns. Use visible buttons, segmented controls, tabs, chips, or drawers.
- Route labels should match user intent: Applications, Documents, Review, Verify, Formats, Connect, Reports, Admin.
- Role-based visibility is preferred over showing every Super Admin tool to every reviewer.

### Enterprise Shell

- Left rail groups navigation by operator intent: Main, Intelligence, Administration.
- Each nav item carries an English label and Nepali helper label.
- Top bar contains institution context, date range context, global search, notification state, refresh, LipiCore state, and operator identity.
- The top bar must remain compact; page-specific actions belong in the page header or local panel.
- The shell should preserve maximum document/canvas space on template and review screens.
- Default product density is compact enterprise: 12-13px navigation labels, 20-24px page/workspace headings, 40px utility controls, 12-16px panel padding, and 16px section gaps.
- Do not return to horizontal primary navigation tabs. The approved product direction is a persistent operating shell with left-rail wayfinding and page-local tabs only where they switch content inside one module.
- On narrow widths, the shell may collapse into a compact stacked navigation strip, but the same grouped information architecture must remain visible and must not cause horizontal overflow.

### Approved Mockup Patterns

- Operations Overview: KPI signals across the top, workflow funnel, case trend, document type mix, SLA/compliance risk, reviewer workload, recent cases, and intelligence summary. This screen should read as an operational command center.
- Review Queue: filterable queue table with priority, confidence, reviewer, status, SLA, and a right-side selected-case preview with extracted key values and quick actions.
- Case Review Workspace: three-zone cockpit with document navigation, large evidence viewer, editable extracted fields, and right-side LipiCore assistance for address, name, duplicate/entity, and field alerts.
- Batches And Uploads: batch health, source filters, processing pipeline, failed-upload visibility, and recent file activity. Upload is a visible primary action.
- Exports: delivery health, export table, retry controls, webhook/SFTP/API receipt status, retry queue, and signed delivery evidence.
- Template Studio: split template library and selected-template detail. Permanent Nepal ID templates are system-governed, while tenant forms remain editable with test-run accuracy before publish.
- Address Intelligence: resolver workspace with fuzzy suggestions, administrative hierarchy, road/tole evidence, legacy VDC mapping, aliases, and reviewed correction history.
- Field Normalization: bilingual raw-to-normalized field list with BS/AD conversion, name normalization, address standardization, PAN/VAT formatting, confidence, source, and approval workflow.
- Integrations Hub: API keys, webhooks, SFTP, endpoints, receipts, retry queue, payload preview, signature verification, and delivery-by-channel health.
- Audit And Compliance: audit events, access logs, policy status, retention rules, approval chain, lifecycle events, and evidence bundle downloads.

## Core Screens

### Command Center

The first viewport must answer:

- Are documents flowing?
- Where are cases stuck?
- Are reviewers overloaded?
- Are exports succeeding?
- Are there compliance or SLA risks?
- Is Nepal-specific intelligence coverage healthy?

Avoid generic metric-only dashboards. The screen should be workflow-first with lanes, bottlenecks, next actions, priority work, integration health, and readiness.

### Case Review Workspace

This is the core product screen. It should feel like a professional review cockpit:

- Left: document viewer with thumbnails, zoom, rotate, raw OCR, evidence boxes, assets such as photo/signature/stamp/thumbprints.
- Center: editable extracted fields grouped by identity, address, dates, contact, document metadata, finance/account fields.
- Right: intelligence assistance for Nepali/English pairs, BS/AD conversion, name candidates, address candidates, entity reconciliation, mismatch warnings.
- Bottom or drawer: audit timeline with upload, OCR, LipiCore extraction, reviewer edits, checker approval, export receipt.

Every field must expose raw value, normalized value, confidence, evidence source, correction state, and audit reason where applicable.

### Template Studio

Template Studio should feel like a Canva-style document editor:

- Large canvas first, minimal chrome.
- Zoom, pan, page thumbnails, add/remove box, drag, resize, rename, duplicate, undo-friendly editing.
- Multipage PDFs save as one template with per-page fields.
- Permanent Nepal identity templates are governed and locked by default.
- Super Admin can revise permanent identity formats; tenant admins manage tenant templates only.
- Show test-run coverage before publish.

### Address And Name Intelligence

Nepal reference intelligence is a first-class differentiator:

- Province, district, municipality/gaunpalika, VDC wording, ward validation.
- Road, street, tole, area evidence.
- Nepali name lexicon and transliteration candidates.
- Suggestions are reviewer-safe choices, not invisible overwrites.
- Store original OCR value, corrected/normalized value, source field or dataset, confidence, and audit reason.

## Copy Rules

- Use LipiCore for the intelligence layer in operator-facing UI.
- Do not expose raw model/provider names in operator UI.
- Do not claim perfect accuracy, full automation, fraud detection, biometric verification, or 99% accuracy unless backed by benchmark data.
- Prefer operational language over marketing language.
- Avoid unexplained words such as cases, packets, evidence, blocks, sync, CBS/LOS refs unless the screen also makes their meaning obvious through context.

## Component Patterns

### Primary Action

- Visible button with icon and text.
- Used for upload, open next review, approve, export, save template, run test.
- Keep actions close to the surface they affect.

### Review Field Row

- Label.
- Raw OCR value.
- Normalized/corrected value.
- Confidence and status.
- Evidence link.
- Candidate choices when available.
- Audit reason when changed.

### Status Card

- Title.
- Metric or status.
- Trend or queue count where useful.
- Click-through target.
- State color based on operational meaning.

### Tables

- Search, filters, saved views, column controls, bulk actions, export.
- Rows must show urgency through color and content: SLA risk, confidence, assigned reviewer, risk flags, source batch, document type.

## Anti-Patterns

- Generic SaaS KPI grids as the main dashboard.
- One giant page containing every feature.
- Dropdowns for primary workflows.
- Decorative sidebars that reduce canvas space.
- Model/provider names in operator UI.
- Template editing that forces tiny image previews.
- Silent correction or translation without preserved originals and audit reason.
- "Unknown document" dead ends. Unknown documents should still get full-page OCR, semantic extraction, and reviewer/template mapping.

## Quality Checklist

- Can an operator identify the next action within five seconds?
- Can a reviewer correct extracted data without leaving the document view?
- Can an auditor see who changed what, when, and why?
- Can a tenant admin understand whether exports are actually delivered?
- Can Super Admin distinguish permanent Nepal identity templates from tenant templates?
- Are Nepali and English values shown as paired fields where relevant?
- Are address/name candidates shown as suggestions with sources?
- Does the layout work at desktop and narrow widths without text overlap or horizontal overflow?
