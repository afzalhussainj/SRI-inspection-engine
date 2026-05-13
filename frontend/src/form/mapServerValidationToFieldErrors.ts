import type { FormSchema } from "../types";
import { fieldById } from "./schemaFields";
import { parseEngineValidationDetail } from "./parseEngineValidationDetail";

export type ServerFieldErrorMap = Record<string, string>;

export function mapServerValidationToFieldErrors(
  schema: FormSchema,
  detail: string,
  fmt: {
    missingSelect: string;
    missingText: string;
    missingNumber: string;
    badNumber: string;
    badText: string;
    badString: string;
    badOption: string;
    unsupported: string;
  }
): { fieldErrors: ServerFieldErrorMap; general: string[] } {
  const fields = fieldById(schema);
  const parsed = parseEngineValidationDetail(detail);
  const fieldErrors: ServerFieldErrorMap = {};
  const general: string[] = [];

  for (const issue of parsed) {
    if (!issue.fieldId) {
      general.push(issue.raw);
      continue;
    }
    const field = fields.get(issue.fieldId);
    switch (issue.kind) {
      case "missing":
        if (field?.type === "select") {
          fieldErrors[issue.fieldId] = fmt.missingSelect;
        } else if (field?.type === "number") {
          fieldErrors[issue.fieldId] = fmt.missingNumber;
        } else {
          fieldErrors[issue.fieldId] = fmt.missingText;
        }
        break;
      case "type_number":
        fieldErrors[issue.fieldId] = fmt.badNumber;
        break;
      case "type_text":
        fieldErrors[issue.fieldId] = fmt.badText;
        break;
      case "type_string":
        fieldErrors[issue.fieldId] = fmt.badString;
        break;
      case "invalid_option":
        fieldErrors[issue.fieldId] = fmt.badOption;
        break;
      case "unsupported":
        fieldErrors[issue.fieldId] = fmt.unsupported;
        break;
      default:
        general.push(issue.raw);
    }
  }

  return { fieldErrors, general };
}
