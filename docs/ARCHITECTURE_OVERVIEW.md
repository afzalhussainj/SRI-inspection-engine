## Architecture Overview (Milestones 1–3)

### Purpose

This system implements a reusable, **configuration-driven inspection engine**. All inspection behavior (form structure, deterministic evaluation rules, output wording/labels) is defined by configuration, not hardcoded logic.

The same engine supports:
- **NRB**: single submission → one PDF → session ends
- **QuietRisk (MVP)**: multiple submissions → aggregation math → one employer-level executive PDF

In the current MVP implementation, an inspection instance is treated as QuietRisk when `organization_id` is set (used for grouping/aggregation). QuietRisk responders do not receive per-submission PDFs.

Constraints (locked):
- Domain-agnostic engine code (no audience/inspection assumptions)
- Deterministic outputs only (no AI, no probabilistic scoring)

---

## System components

### 1) Admin (Django Admin)

**Responsibilities**
- Create and manage inspection entities:
  - inspection instances (templates/campaign runs)
  - config versions (draft → publish → immutable)
  - recipient links (public tokens)
- View submissions and generated artifacts (PDF files).

**Key invariants**
- Published config versions are immutable.
- Public links should point to a published config version to ensure reproducibility.

### 2) Backend API (Django + DRF)

**Responsibilities**
- Public endpoints to:
  - fetch form schema for a recipient link
  - submit answers for a recipient link
  - fetch generated PDF for a submission (NRB)
- Enforcement:
  - link validity (exists, not expired)
  - published-only configs for public reads
  - deterministic validation + deterministic evaluation
  - QuietRisk PDF restriction (respondents cannot download PDFs)

### 3) Rules Engine (deterministic)

**Responsibilities**
- Validate answers against `config.schema` deterministically.
- Evaluate deterministic outputs from `config.evaluation` (classification, tags, patterns, section classifications).

### 4) Aggregation Engine (QuietRisk MVP)

**Responsibilities**
- Group multiple submissions by:
  - `organization_id`
  - `inspection_instance_id`
- Compute:
  - counts by section
  - counts by classification (Cleared/Watch/Elevated)
  - counts by indicator tags
  - top repeated risk patterns
- Generate one employer-level executive PDF (no individual PDFs to HR).

### 5) PDF Layer (fixed template)

**Responsibilities**
- Generate reproducible PDFs using a fixed layout template.
- Dynamic content is limited to (Operating Rules):
  - section name
  - classification (reader-facing labels use standard title-style formatting; stored evaluation values remain `Cleared` / `Watch` / `Elevated`)
  - selected output language
  - counts (aggregated only)
- Present selected structural considerations as **plain narrative bullets** (no mechanical “Question 1 / Question 2” prefixes in reader-facing sections). `question_number` may still exist in stored outputs for traceability.
- Rotate a small **deterministic set** of domain narrative lead sentences by domain order so repeated openings are reduced without changing evaluation results.

**Artifacts**
- NRB: parent PDF generated on demand from the submission/config snapshot and streamed for download.
- QuietRisk: aggregated PDF generated on demand from campaign counts and streamed from admin.

**Determinism (Milestone 3)**
- PDFs are generated via ReportLab and hardened to avoid run-to-run timestamp drift (best-effort fixed metadata).
- Reproducibility is tied to immutable published config versions and deterministic rendering inputs.

**QuietRisk access rule (client clarification)**
- QuietRisk respondents do **not** generate PDFs and do **not** have public PDF download endpoints.
- The employer-level executive PDF is generated and downloaded from the **admin layer** only.

### 6) Frontend (React)

**Responsibilities**
- Render the form dynamically from the backend-provided schema.
- Submit answers back to backend.
- Display deterministic error states (expired link, invalid link, unpublished config, network/API failure).
- When a link is **already submitted**, show a **confirmation-style** completion state (not a disabled-error pattern); keep optional public PDF download visible for **NRB** only when the API allows it (no broken PDF button for QuietRisk).
- Apply **default public branding** when no organization record applies: program name **SRI Program**, footer line **Structured Risk Inspection Technology** (overridden by **Organization Branding** when configured). Internal ownership naming is **not** used as public footer copy.
- Place inspection/link/version identifiers in a collapsed **Reference details** disclosure at the bottom of the page (support use), not as prominent “session” headings.
- Allow selecting an output language when the config provides multiple options.

---

## Data flow (end-to-end)

### A) Admin defines inspection → publish version
1. Admin creates/edits a **draft** config version.
2. Admin **publishes** the config version, making it immutable.

### B) Admin creates recipient links (public)
1. Admin creates a `recipient_link` for a specific inspection run.
2. Each link is pinned to a specific published `config_version_id`.
3. Admin shares the public URL with the respondent(s).

### C) Respondent loads and submits
1. Frontend calls backend to fetch schema for the link.
2. Backend validates link + config version, returns schema JSON.
3. Frontend renders the form.
4. Frontend submits answers.
5. Backend validates answers deterministically, evaluates deterministic outputs, stores submission.
6. For **NRB**, a single-submission PDF is generated **on demand** when downloaded (not necessarily during submit); the public PDF endpoint applies only when the instance has **no** `organization_id`. For **QuietRisk**, respondents do **not** receive public PDFs; parent PDFs are obtained through admin workflows.

### D) QuietRisk aggregation (MVP)
1. Multiple respondents submit under the same `inspection_instance_id + organization_id`.
2. An admin generates the aggregated report PDF from the admin layer when ready (client clarification).

---

## Public API endpoints (current)

All endpoints are served under `/api/`.

### Health
- `GET /api/health/`

### Public inspection (NRB + QuietRisk responders)
- `GET /api/public/inspections/{inspection_id}/links/{link_uuid}/`
  - Returns: `schema`, `config_version_id`, link metadata, and optional output language options:
    - `output_languages`
    - `default_output_language`
- `POST /api/public/inspections/{inspection_id}/links/{link_uuid}/submit/`
  - Body: `{ "answers": {...}, "output_language": "en" }` (output_language optional; defaults from config)
  - Returns: a simple submission status payload (respondents do not receive classifications or evaluation outputs).
- `GET /api/public/inspections/{inspection_id}/links/{link_uuid}/pdf/`
  - Downloads the single-submission PDF (NRB only). For QuietRisk, returns 403.

---

## Runtime configuration (practical)

### Backend
- `DEBUG=true|false`
- `FRONTEND_BASE_URL` (used to generate copy-pasteable public links in admin)
- `MEDIA_ROOT` / `MEDIA_URL` (stores generated PDFs)
- CORS is enabled in `DEBUG` to allow the Vite dev server to call the backend directly.

### Frontend
- `VITE_API_BASE_URL` (optional). If not set, frontend calls `http://127.0.0.1:8000` by default.

---

## Core entities (conceptual)

- **InspectionInstance**
  - A concrete inspection run/campaign (QuietRisk uses this for grouping/closing).
  - May also represent a template baseline to clone from (implementation detail).
- **InspectionConfigVersion**
  - Versioned config snapshot (draft/published), immutable once published.
- **RecipientLink**
  - Public token; one recipient uses one link.
- **Submission**
  - Stores answers + deterministic outputs; pinned to a config version.
- **AggregatedReport**
  - Stores aggregation counts + employer PDF (QuietRisk MVP).

