import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { GetFormResponse } from "./types";
import { FormPage } from "./FormPage";

const getForm = vi.fn();
const submitForm = vi.fn();
const fetchSubmissionPdf = vi.fn();

vi.mock("./api", () => ({
  getForm: (...args: unknown[]) => getForm(...args),
  submitForm: (...args: unknown[]) => submitForm(...args),
  fetchSubmissionPdf: (...args: unknown[]) => fetchSubmissionPdf(...args),
  resolveMediaUrl: () => null
}));

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
              options: [{ value: "one", label: "One" }]
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

    await user.click(screen.getByRole("button", { name: /^submit$/i }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /submission received/i })).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: /already submitted/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /download pdf summary/i })).toBeEnabled();
  });
});
