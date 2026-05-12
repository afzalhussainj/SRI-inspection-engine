## Admin Publish Flow (Milestones 1–3)

This document describes the workflow of draft → publish → immutable versioning (Operating Rules).

---

## 1) Entities

- **InspectionInstance**: a container for an inspection run/campaign (**campaign**) or a reusable baseline (**template**).
- **InspectionConfigVersion**: stores the JSON config snapshot and status.
- **RecipientLink**: public token pinned to a config version.

---

## 1.1) Template vs Campaign (practical meaning)

- **Template**
  - A reusable “starting point” inspection instance.
  - You edit/build questions and rules on a draft config version under this instance.
  - You typically clone templates to create new campaigns.

- **Campaign**
  - The “live run” you send to recipients.
  - Recipient links are created for campaigns.
  - For QuietRisk campaigns, set:
    - `organization_id` (required for aggregation)
    - `closes_at` and/or `submission_threshold` (aggregation triggers)

In the current MVP implementation, setting `organization_id` is what marks a campaign as QuietRisk for PDF access rules (respondents cannot download PDFs).

---

## 2) Draft workflow

1. Admin creates an `InspectionInstance`.
2. Admin creates an `InspectionConfigVersion` in `draft`.
3. Admin edits the config JSON (schema + deterministic evaluation rules).

Draft can be edited freely.

---

## 3) Publish workflow

Publishing a config version:
- sets `status = published`
- sets `published_at`
- computes and stores an immutable hash (e.g., sha256 of normalized JSON)

After publish:
- the config version is immutable (changes should be rejected)
- new changes must be a new draft version that is later published

---

## 4) Pinning rules (reproducibility)

- When creating public links, each `RecipientLink` is pinned to a specific `config_version_id`.
- Public endpoints should only serve schema for **published** pinned versions.
- Submissions store the exact config version used so PDFs/outputs can be reproduced.

---

## 5) Practical admin steps

### A) NRB (single submission)
1. Create/edit config version in Draft (questions + rules).
2. Publish the config version (locks it + computes sha256 hash).
3. Create recipient links pinned to that published version.
4. Share the public URLs with recipients.
5. Each recipient can submit once.
6. A single-submission PDF is generated on demand from the submission/config snapshot and downloaded from admin.

### B) QuietRisk (aggregated)
1. Create a Campaign (usually by cloning from a Template using the `InspectionInstance` admin action).
2. Set the campaign `organization_id`.
3. Optionally set `closes_at` and/or `submission_threshold` (operational triggers). The system does not auto-run aggregation by default; these are used for admin workflows (e.g., link expiry) or an external admin process.
4. Publish the campaign’s config version.
5. Create multiple recipient links (one per respondent).
6. Respondents submit (responses are inputs only; respondents do not generate/download PDFs).
7. Admin generates the aggregated report PDF from the admin layer when ready (Milestone 3).
8. One employer-level aggregated PDF can be generated and downloaded from the admin UI.

---

## 6) Notes / guardrails enforced by the system

- Recipient links can only be created for **published** config versions.
- Public endpoints serve form schema only for **published** pinned versions.
- Published config versions are immutable; changes require a new draft + publish.
- QuietRisk respondents cannot download PDFs from public endpoints (403 on `/pdf/`).

---

## 7) Admin shortcuts (current UI)

### `InspectionInstance` actions
- **Clone selected as new template(s)**: creates new template instances + copies latest config.
- **Create campaign(s) from selected template(s)**: creates new campaign instances + copies latest config.
- **Generate aggregated PDF now (campaigns only)**: generates/updates the `AggregatedReport` for selected campaigns.

### `InspectionConfigVersion` actions
- **Publish selected config versions**: publishes draft versions (computes sha256 + published_at).
- **Create recipient link(s) for selected config versions**: creates recipient links only for published versions and shows an example full URL.

