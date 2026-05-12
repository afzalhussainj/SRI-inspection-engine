## Rules Engine Definition (Milestone 2)

This document defines deterministic evaluation logic and constraints (Operating Rules).

---

## 1) Constraints (locked)

- Engine logic is domain-agnostic (no inspection-specific assumptions).
- No AI inference or probabilistic scoring.
- Deterministic outputs only.
- All inspection meaning comes from configuration.

---

## 2) Inputs

### Config
The engine accepts a JSON config (see `docs/CONFIG_SPECIFICATION.md`).

### Answers
Answers are a JSON object:
- keys are field ids (`schema.sections[].fields[].id`)
- values are typed per field type:
  - `text` → string
  - `number` → integer/float

---

## 3) Validation (deterministic)

Validation checks:
- required fields must be present and not empty
- types must match the field type
- select fields must be one of the configured option `value`s

Validation must be deterministic:
- same answers/config → same error results
- stable error ordering

---

## 4) Evaluation (deterministic outputs)

The engine produces:
- `classification`: overall classification (`Cleared` / `Watch` / `Elevated`)
- `tags`: indicator tags (unique sorted strings)
- `patterns`: identifiers of matched classification rules, taken from `evaluation.classification.rules[].id` (unique sorted strings)
- `section_classifications`: mapping of section id → classification

Deterministic rule policy:
- Start with `evaluation.classification.default` (default `Cleared`).
- Evaluate rules strictly in the array order as stored in the **published config version** (`evaluation.classification.rules`). The engine does not reorder rules.
- If a rule matches, apply its `then` classification.
- The “last matching rule wins” rule is deterministic.

Severity ordering (config-driven, separate from rule evaluation order):
- If `evaluation.classification.order` is provided, it defines the severity order used when promoting section-level classifications.
- If not provided, the system derives a deterministic order from the default + rule `then` values (appearance order).
- This severity ordering does **not** affect rule evaluation order (which is always the `rules[]` array order in the published config).

Tag rules:
- Evaluate each tag rule independently.
- When a rule matches, add its tag list.
- Store tags as unique sorted strings.

### Public API note
For respondents, evaluation outputs are stored with the submission but are **not returned** in the public submit response payload.

---

## 5) Aggregation signals (QuietRisk MVP)

QuietRisk aggregation requires deterministic signals per submission:
- classification
- tags
- patterns
- section classifications

These signals are used to compute aggregation counts without storing employee identity.

