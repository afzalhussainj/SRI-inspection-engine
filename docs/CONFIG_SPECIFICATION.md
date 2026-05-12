## Config Specification (Milestones 1–3)

This document defines the configuration schema used by the inspection engine. **All inspection meaning comes from configuration** (Operating Rules).

The configuration is stored as a JSON object inside a **versioned, immutable** record after publish.

---

## 1) Top-level structure

- `schema` *(object, required)*: form definition (sections + fields)
- `output` *(object, optional)*: output-language copy used by the PDF layer *(Operating Rules: “selected output language” is allowed dynamic content)*
- `evaluation` *(object, optional)*: deterministic rules to compute outputs

Example config is included at the end of this document.

---

## 2) `schema`

### `schema.title` *(string)*
Human-facing title of the inspection.

### `schema.sections` *(array of section objects)*

Each section object:
- `id` *(string, required)*: stable identifier (used in outputs/aggregation)
- `title` *(string, required)*: section name (allowed PDF dynamic content)
- `fields` *(array of field objects, required)*

### Field object (question)

Each field object:
- `id` *(string, required)*: stable identifier (used as key in `answers`)
- `type` *(string, required)*: supported types:
  - `text`
  - `number`
  - `select` *(single-choice)*
- `label` *(string, required)*: UI label
- `required` *(boolean, required)*: whether input is required

#### `select` field options

If `type = "select"`, the field must include:
- `options` *(array, required)*: list of `{ "value": string, "label": string }`

Notes:
- `value` is what gets stored in `answers[field_id]`.
- `label` is what the user sees in the dropdown.

Notes:
- Field ids must be unique within the config.
- Section ids must be unique within the config.

---

## 3) `evaluation` (deterministic)

### `evaluation.classification`

- `default` *(string)*: default classification (commonly `Cleared`)
- `order` *(array of strings, optional)*: severity order for section-level promotion/aggregation (config-driven)
- `rules` *(array)*: ordered rules

Each rule:
- `id` *(string, optional but recommended)*: stable pattern identifier
- `if` *(condition object)*: deterministic condition
- `then` *(string)*: one of:
  - `Cleared`
  - `Watch`
  - `Elevated`

Deterministic behavior:
- Rules are evaluated strictly in the array order as stored in the **published config version** (`evaluation.classification.rules`). The engine does not reorder rules.
- The last matching rule wins (simple deterministic policy).

### `evaluation.tags`

Array of tag rules. Each rule:
- `if` *(condition object)*
- `add` *(array of strings)*: tags to attach if matched

Tags are stored deterministically as unique sorted strings.

---

## 4) Condition language (deterministic)

Supported:

Logical composition:
- `{ "and": [cond, cond, ...] }`
- `{ "or": [cond, cond, ...] }`
- `{ "not": cond }`

Field comparisons:
- `{ "field": "stress_level", "op": ">=", "value": 8 }`

Supported operators:
- `exists`
- `==`, `!=`
- `>`, `>=`, `<`, `<=` *(numeric only)*

---

## 5) `output` (PDF copy by language)

This section is **optional**. If present, it allows selecting a language at submission time and including **only the selected language copy** in PDFs (plus allowed dynamic content like section names/classification/counts).

**Display vs stored values:** Parent-facing PDFs may apply **presentation-only** formatting (for example title-style classification labels and plain consideration bullets without “Question N” prefixes). Published configuration JSON and stored submission `outputs` continue to use the canonical deterministic classification strings produced by the engine (`Cleared`, `Watch`, `Elevated`, etc.).

Supported shape:

- `output.default_language` *(string, optional)*: e.g. `"en"`
- `output.languages` *(array of strings, optional)*: e.g. `["en", "es"]`
- `output.copy` *(object, optional)*: language → copy
  - `output.copy[lang].intro` *(string, optional)*
  - `output.copy[lang].sections` *(object, optional)*: section_id → paragraph text

### How language selection is used (current API)
- `GET /api/public/inspections/{inspection_id}/links/{link_uuid}/` returns:
  - `output_languages`
  - `default_output_language`
- `POST /api/public/inspections/{inspection_id}/links/{link_uuid}/submit/` accepts:
  - `output_language` (optional; defaults to `output.default_language`)

---

## 5) Versioning rules

- Draft configs can be edited.
- Publish creates a published version which becomes immutable.
- Public inspection runs must be pinned to a published version.

---

## 6) Example config

```json
{
  "schema": {
    "title": "Initial Inspection Template",
    "sections": [
      {
        "id": "profile",
        "title": "Profile",
        "fields": [
          { "id": "full_name", "type": "text", "label": "Full name", "required": true },
          { "id": "age", "type": "number", "label": "Age", "required": false }
        ]
      },
      {
        "id": "self_report",
        "title": "Self report",
        "fields": [
          {
            "id": "sleep_hours",
            "type": "number",
            "label": "Average sleep hours (last 7 days)",
            "required": false
          },
          {
            "id": "stress_level",
            "type": "number",
            "label": "Stress level (0-10)",
            "required": false
          }
        ]
      }
    ]
  },
  "output": {
    "default_language": "en",
    "languages": ["en"],
    "copy": {
      "en": {
        "intro": "This report summarizes your inspection results.",
        "sections": {
          "profile": "Profile section summary text (config-provided).",
          "self_report": "Self report section summary text (config-provided)."
        }
      }
    }
  },
  "evaluation": {
    "classification": {
      "default": "Cleared",
      "rules": [
        { "id": "stress_elevated", "if": { "field": "stress_level", "op": ">=", "value": 8 }, "then": "Elevated" },
        { "id": "stress_watch", "if": { "field": "stress_level", "op": ">=", "value": 5 }, "then": "Watch" }
      ]
    },
    "tags": [
      { "if": { "field": "sleep_hours", "op": "<", "value": 6 }, "add": ["low_sleep"] }
    ]
  }
}
```

