## Aggregation Model (QuietRisk MVP, Milestone 3)

This document defines how multiple submissions are grouped and summarized (Operating Rules).

---

## 1) Grouping keys

For aggregated inspections, each submission must be tied to a single:
- `organization_id`
- `inspection_instance_id`

No employee identity is stored.

---

## 2) Aggregation triggers (client clarification)

Aggregated report PDF generation is performed from the **admin layer**.

If you want to use close/threshold as operational triggers, that should be done by an admin process (manual admin action or a scheduled job run by the organization), not by respondents.

---

## 3) Required aggregation outputs (MVP)

The engine must compute:

### A) Counts by section
For each section:
- number of submissions classified as Cleared/Watch/Elevated (canonical keys in stored outputs and in the aggregated count structure; employer-facing PDFs use the same tier labels for display).

### B) Counts by classification
Overall counts:
- Cleared
- Watch
- Elevated

### C) Counts by indicator tags
Across all submissions:
- total count per tag

### D) Top repeated risk patterns
Across all submissions:
- most frequent patterns (pattern identifiers are derived from matched classification rule IDs: `evaluation.classification.rules[].id`)
- deterministic ordering (e.g., by count desc then key asc)

---

## 4) Output artifact

- One employer-level executive PDF (no dashboards, no logins, no drilldowns).
- No individual PDFs delivered to HR.

## 5) Access / generation (client clarification)

- Aggregated PDF generation is performed from the **admin layer**.
- Respondents do not generate PDFs and do not have public PDF download endpoints.

### Practical generation (current implementation)
- Admin runs aggregation from the `InspectionInstance` list view action: **“Generate aggregated PDF now (campaigns only)”**.
- The system creates or updates one `AggregatedReport` per campaign and stores deterministic counts (`counts`).
- The aggregated PDF is rendered on demand from those counts when the admin downloads it.
- Admin downloads the PDF from the `AggregatedReport` admin UI (admin-only stream).
