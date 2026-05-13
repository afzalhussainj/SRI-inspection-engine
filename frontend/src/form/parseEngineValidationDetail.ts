/**
 * Parses Django/engine validation messages returned as a single `detail` string
 * (see backend `validate_answers`: errors joined with "; ").
 */

export type ParsedValidationIssue = {
  fieldId: string;
  /** coarse category for friendly copy */
  kind: "missing" | "type_text" | "type_number" | "type_string" | "invalid_option" | "unsupported" | "unknown";
  raw: string;
};

const RE_MISSING = /^Missing required field:\s*(.+)$/i;
const RE_TEXT = /^Field\s+(.+?)\s+must be text\.?$/i;
const RE_NUMBER = /^Field\s+(.+?)\s+must be a number\.?$/i;
const RE_STRING = /^Field\s+(.+?)\s+must be a string\.?$/i;
const RE_ONE_OF = /^Field\s+(.+?)\s+must be one of\s+/i;
const RE_UNSUPPORTED = /^Unsupported field type for\s+(.+?):\s*(.+)$/i;

export function parseEngineValidationDetail(detail: string): ParsedValidationIssue[] {
  const parts = detail
    .split(";")
    .map((s) => s.trim())
    .filter(Boolean);
  const out: ParsedValidationIssue[] = [];

  for (const raw of parts) {
    let m = raw.match(RE_MISSING);
    if (m?.[1]) {
      out.push({ fieldId: m[1].trim(), kind: "missing", raw });
      continue;
    }
    m = raw.match(RE_TEXT);
    if (m?.[1]) {
      out.push({ fieldId: m[1].trim(), kind: "type_text", raw });
      continue;
    }
    m = raw.match(RE_NUMBER);
    if (m?.[1]) {
      out.push({ fieldId: m[1].trim(), kind: "type_number", raw });
      continue;
    }
    m = raw.match(RE_STRING);
    if (m?.[1]) {
      out.push({ fieldId: m[1].trim(), kind: "type_string", raw });
      continue;
    }
    m = raw.match(RE_ONE_OF);
    if (m?.[1]) {
      out.push({ fieldId: m[1].trim(), kind: "invalid_option", raw });
      continue;
    }
    m = raw.match(RE_UNSUPPORTED);
    if (m?.[1]) {
      out.push({ fieldId: m[1].trim(), kind: "unsupported", raw });
      continue;
    }
    out.push({ fieldId: "", kind: "unknown", raw });
  }
  return out;
}
