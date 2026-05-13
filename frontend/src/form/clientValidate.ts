import type { FieldSchema, FormSchema } from "../types";
import { iterFields } from "./schemaFields";

function isEmpty(val: unknown): boolean {
  return val === undefined || val === null || val === "";
}

function selectHasRealValue(field: FieldSchema, val: unknown): boolean {
  if (typeof val !== "string" || val === "") return false;
  const allowed = new Set((field.options ?? []).map((o) => o.value));
  return allowed.has(val);
}

/**
 * Client-side checks aligned with backend `validate_answers` expectations.
 * Returns per-field messages (field id -> message).
 */
export function validateAnswersForSubmit(
  schema: FormSchema,
  answers: Record<string, unknown>,
  messages: {
    requiredSelect: string;
    requiredText: string;
    requiredNumber: string;
    invalidNumber: string;
  }
): Record<string, string> {
  const errors: Record<string, string> = {};

  for (const field of iterFields(schema)) {
    const val = answers[field.id];
    if (!field.required) {
      if (field.type === "number" && !isEmpty(val) && typeof val !== "number") {
        errors[field.id] = messages.invalidNumber;
      }
      continue;
    }

    if (field.type === "select") {
      if (!selectHasRealValue(field, val)) {
        errors[field.id] = messages.requiredSelect;
      }
      continue;
    }

    if (field.type === "number") {
      if (isEmpty(val)) {
        errors[field.id] = messages.requiredNumber;
      } else if (typeof val !== "number" || Number.isNaN(val)) {
        errors[field.id] = messages.invalidNumber;
      }
      continue;
    }

    if (isEmpty(val) || (typeof val === "string" && val.trim() === "")) {
      errors[field.id] = messages.requiredText;
    }
  }

  return errors;
}

/** Payload sent to the API: never includes empty strings or placeholder-only values. */
export function scrubAnswersForSubmit(schema: FormSchema, answers: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const field of iterFields(schema)) {
    const val = answers[field.id];
    if (val === undefined || val === null || val === "") continue;
    if (field.type === "select" && typeof val === "string" && !selectHasRealValue(field, val)) continue;
    out[field.id] = val;
  }
  return out;
}
