import type { FieldSchema, FormSchema } from "../types";

function isAllowedSelectValue(field: FieldSchema, value: string): boolean {
  const opts = field.options ?? [];
  return opts.some((o) => o.value === value);
}

/**
 * Initial answer map from schema: only includes keys when the backend provided a valid `default`
 * that matches the field type and (for selects) the configured option list.
 */
export function buildInitialAnswers(schema: FormSchema): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const section of schema.sections) {
    for (const field of section.fields) {
      const raw = field.default;
      if (raw === undefined || raw === null) continue;

      if (field.type === "select") {
        const v = typeof raw === "number" ? String(raw) : typeof raw === "string" ? raw : "";
        if (v && isAllowedSelectValue(field, v)) {
          out[field.id] = v;
        }
        continue;
      }

      if (field.type === "number") {
        if (typeof raw === "number" && !Number.isNaN(raw)) {
          out[field.id] = raw;
        } else if (typeof raw === "string" && raw.trim() !== "") {
          const n = Number(raw);
          if (!Number.isNaN(n)) out[field.id] = n;
        }
        continue;
      }

      if (field.type === "text" && typeof raw === "string") {
        out[field.id] = raw;
      }
    }
  }
  return out;
}
