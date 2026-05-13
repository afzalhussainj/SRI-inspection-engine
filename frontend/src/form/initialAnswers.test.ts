import { describe, it, expect } from "vitest";
import { buildInitialAnswers } from "./initialAnswers";
import type { FormSchema } from "../types";

describe("buildInitialAnswers", () => {
  it("returns empty object when no defaults", () => {
    const schema: FormSchema = {
      title: "T",
      sections: [
        {
          id: "s",
          title: "S",
          fields: [
            {
              id: "f",
              type: "select",
              label: "L",
              required: true,
              options: [{ value: "v1", label: "One" }]
            }
          ]
        }
      ]
    };
    expect(buildInitialAnswers(schema)).toEqual({});
  });

  it("uses default only when value is in option list", () => {
    const schema: FormSchema = {
      title: "T",
      sections: [
        {
          id: "s",
          title: "S",
          fields: [
            {
              id: "f",
              type: "select",
              label: "L",
              required: true,
              options: [{ value: "v1", label: "One" }],
              default: "v1"
            }
          ]
        }
      ]
    };
    expect(buildInitialAnswers(schema)).toEqual({ f: "v1" });
  });

  it("ignores default not in option list", () => {
    const schema: FormSchema = {
      title: "T",
      sections: [
        {
          id: "s",
          title: "S",
          fields: [
            {
              id: "f",
              type: "select",
              label: "L",
              required: true,
              options: [{ value: "v1", label: "One" }],
              default: "nope"
            }
          ]
        }
      ]
    };
    expect(buildInitialAnswers(schema)).toEqual({});
  });
});
