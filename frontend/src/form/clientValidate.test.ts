import { describe, it, expect } from "vitest";
import { scrubAnswersForSubmit, validateAnswersForSubmit } from "./clientValidate";
import type { FormSchema } from "../types";

const schema: FormSchema = {
  title: "T",
  sections: [
    {
      id: "s",
      title: "S",
      fields: [
        {
          id: "q_select",
          type: "select",
          label: "Pick",
          required: true,
          options: [
            { value: "a", label: "A" },
            { value: "b", label: "B" }
          ]
        },
        {
          id: "q_opt",
          type: "select",
          label: "Optional",
          required: false,
          options: [{ value: "x", label: "X" }]
        }
      ]
    }
  ]
};

const msgs = {
  requiredSelect: "sel-req",
  requiredText: "txt-req",
  requiredNumber: "num-req",
  invalidNumber: "num-inv"
};

describe("clientValidate", () => {
  it("flags required select when empty string", () => {
    const err = validateAnswersForSubmit(schema, { q_select: "" }, msgs);
    expect(err.q_select).toBe("sel-req");
  });

  it("flags required select when key missing", () => {
    const err = validateAnswersForSubmit(schema, {}, msgs);
    expect(err.q_select).toBe("sel-req");
  });

  it("does not flag optional select when unset", () => {
    const err = validateAnswersForSubmit(schema, { q_select: "a" }, msgs);
    expect(err.q_opt).toBeUndefined();
  });

  it("scrub omits empty and invalid placeholder values", () => {
    const payload = scrubAnswersForSubmit(schema, { q_select: "", q_opt: "" });
    expect(payload).toEqual({});
  });

  it("scrub keeps valid select answers", () => {
    const payload = scrubAnswersForSubmit(schema, { q_select: "b", q_opt: "x" });
    expect(payload).toEqual({ q_select: "b", q_opt: "x" });
  });
});
