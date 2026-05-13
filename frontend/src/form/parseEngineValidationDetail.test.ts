import { describe, it, expect } from "vitest";
import { parseEngineValidationDetail } from "./parseEngineValidationDetail";

describe("parseEngineValidationDetail", () => {
  it("parses multiple missing required fields", () => {
    const parts = parseEngineValidationDetail("Missing required field: a; Missing required field: b");
    expect(parts).toEqual([
      { fieldId: "a", kind: "missing", raw: "Missing required field: a" },
      { fieldId: "b", kind: "missing", raw: "Missing required field: b" }
    ]);
  });

  it("parses field type errors", () => {
    const parts = parseEngineValidationDetail("Field q1 must be a number.");
    expect(parts[0]).toMatchObject({ fieldId: "q1", kind: "type_number" });
  });
});
