import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { GetFormResponse } from "./types";
import { ApiHttpError } from "./api";
import { FormPage } from "./FormPage";

const getForm = vi.fn();
const submitForm = vi.fn();
const fetchSubmissionPdf = vi.fn();

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return {
    ...actual,
    getForm: (...args: unknown[]) => getForm(...args),
    submitForm: (...args: unknown[]) => submitForm(...args),
    fetchSubmissionPdf: (...args: unknown[]) => fetchSubmissionPdf(...args),
    resolveMediaUrl: () => null
  };
});

function minimalForm(overrides: Partial<GetFormResponse> = {}): GetFormResponse {
  return {
    inspection_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    link_uuid: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    config_version_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    expires_at: null,
    already_submitted: false,
    schema: {
      title: "Demo questionnaire",
      sections: [
        {
          id: "sec1",
          title: "Section",
          fields: [
            {
              id: "field_a",
              type: "select",
              label: "Pick",
              required: true,
              options: [
                { value: "one", label: "One" },
                { value: "two", label: "Two" }
              ]
            }
          ]
        }
      ]
    },
    output_languages: ["en", "es"],
    default_output_language: "en",
    selected_content_language: "en",
    branding: {
      organization_id: "",
      hospital_program_name: "SRI Program",
      logo_url: null,
      primary_color: "#1F2937",
      tagline: "",
      footer_text: ""
    },
    ...overrides
  };
}

function renderAtPath(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/:inspectionId/:uuid" element={<FormPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("FormPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("shows confirmation for already-submitted link (no org) and offers PDF", async () => {
    getForm.mockResolvedValue(minimalForm({ already_submitted: true }));

    renderAtPath("/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/11111111-1111-4111-8111-111111111111");

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /submission received/i })).toBeInTheDocument();
    });

    expect(
      screen.getByText(/this inspection link has already been completed/i)
    ).toBeInTheDocument();

    expect(screen.queryByText(/session identifiers/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/config version/i)).not.toBeInTheDocument();

    expect(screen.getByRole("button", { name: /download pdf summary/i })).toBeEnabled();

    expect(screen.getByText(/reference details/i)).toBeInTheDocument();
  });

  it("does not show a PDF download button for org-linked campaigns (QuietRisk-style)", async () => {
    getForm.mockResolvedValue(
      minimalForm({
        already_submitted: true,
        branding: {
          organization_id: "org-quiet-risk",
          hospital_program_name: "Hospital Program",
          logo_url: null,
          primary_color: "#112233",
          tagline: "",
          footer_text: "Footer"
        }
      })
    );

    renderAtPath("/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/22222222-2222-4222-8222-222222222222");

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /submission received/i })).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /download pdf summary/i })).not.toBeInTheDocument();
    });
    expect(screen.getByText(/summaries for this program are provided/i)).toBeInTheDocument();
  });

  it("renders interactive form when link is not yet submitted", async () => {
    getForm.mockResolvedValue(minimalForm({ already_submitted: false }));
    submitForm.mockResolvedValue({ status: "submitted" });

    renderAtPath("/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/33333333-3333-4333-8333-333333333333");

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /^submit$/i })).toBeInTheDocument();
    });

    expect(screen.queryByRole("heading", { name: /submission received/i })).not.toBeInTheDocument();
  });

  it("after submit, shows submission received without disabled-looking prior-submit label", async () => {
    getForm.mockResolvedValue(minimalForm({ already_submitted: false }));
    submitForm.mockResolvedValue({ status: "submitted" });
    const user = userEvent.setup();

    renderAtPath("/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/44444444-4444-4444-a444-444444444444");

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /^submit$/i })).toBeInTheDocument();
    });

    await user.selectOptions(await screen.findByLabelText(/pick/i), "one");

    await user.click(screen.getByRole("button", { name: /^submit$/i }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /submission received/i })).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: /already submitted/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /download pdf summary/i })).toBeEnabled();
  });

  it("required select starts on placeholder, not first real option", async () => {
    getForm.mockResolvedValue(minimalForm());
    renderAtPath("/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/55555555-5555-4555-8555-555555555555");

    const sel = await screen.findByLabelText(/pick/i);
    expect((sel as HTMLSelectElement).value).toBe("");
  });

  it("does not call submit when required select is left on placeholder", async () => {
    getForm.mockResolvedValue(minimalForm());
    const user = userEvent.setup();
    renderAtPath("/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/66666666-6666-4666-8666-666666666666");

    await screen.findByLabelText(/pick/i);
    await user.click(screen.getByRole("button", { name: /^submit$/i }));

    await waitFor(() => {
      expect(screen.getByText(/please select an option/i)).toBeInTheDocument();
    });
    expect(submitForm).not.toHaveBeenCalled();
  });

  it("submits scrubbed answers without empty select value", async () => {
    getForm.mockResolvedValue(minimalForm());
    submitForm.mockResolvedValue({ status: "submitted" });
    const user = userEvent.setup();
    renderAtPath("/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/77777777-7777-4777-8777-777777777777");

    await user.selectOptions(await screen.findByLabelText(/pick/i), "two");
    await user.click(screen.getByRole("button", { name: /^submit$/i }));

    await waitFor(() => {
      expect(submitForm).toHaveBeenCalled();
    });
    const payload = submitForm.mock.calls[0][2] as Record<string, unknown>;
    expect(payload).toEqual({ field_a: "two" });
  });

  it("maps backend 400 validation detail to a field message", async () => {
    getForm.mockResolvedValue(minimalForm());
    submitForm.mockRejectedValue(new ApiHttpError(400, "Missing required field: field_a"));
    const user = userEvent.setup();
    renderAtPath("/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/88888888-8888-4888-8888-888888888888");

    await user.selectOptions(await screen.findByLabelText(/pick/i), "one");
    await user.click(screen.getByRole("button", { name: /^submit$/i }));

    await waitFor(() => {
      expect(screen.getByText(/please select an option/i)).toBeInTheDocument();
    });
  });

  it("shows friendly load failure and retry for network errors", async () => {
    getForm.mockRejectedValue(new TypeError("NETWORK"));
    renderAtPath("/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/99999999-9999-4999-8999-999999999999");

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/connection problem/i);
    });
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("prevents double submission while submit is in flight", async () => {
    getForm.mockResolvedValue(minimalForm());
    let resolveSubmit!: (v: unknown) => void;
    submitForm.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSubmit = resolve;
        })
    );
    const user = userEvent.setup();
    renderAtPath("/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/aaaaaaaa-bbbb-4ccc-addd-eeeeeeeeeeee");

    await user.selectOptions(await screen.findByLabelText(/pick/i), "one");
    const btn = screen.getByRole("button", { name: /^submit$/i });
    await user.click(btn);
    await user.click(btn);
    expect(submitForm).toHaveBeenCalledTimes(1);
    resolveSubmit!({ status: "submitted" });
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /submission received/i })).toBeInTheDocument();
    });
  });
});
