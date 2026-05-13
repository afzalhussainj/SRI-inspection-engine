import type { FieldSchema, FormSchema } from "../types";

export function iterFields(schema: FormSchema): FieldSchema[] {
  const out: FieldSchema[] = [];
  for (const s of schema.sections) {
    for (const f of s.fields) {
      out.push(f);
    }
  }
  return out;
}

export function fieldById(schema: FormSchema): Map<string, FieldSchema> {
  const m = new Map<string, FieldSchema>();
  for (const f of iterFields(schema)) {
    m.set(f.id, f);
  }
  return m;
}
