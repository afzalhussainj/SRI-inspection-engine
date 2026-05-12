import type { GetFormResponse, SubmitResponse } from "./types";

export function apiBaseUrl(): string {
  const fromEnv = import.meta.env.VITE_API_BASE_URL;
  if (fromEnv != null && String(fromEnv).trim() !== "") {
    return String(fromEnv).replace(/\/$/, "");
  }
  // Production bundle served by Django: same-origin `/api`. Local dev: direct backend.
  return import.meta.env.DEV ? "http://127.0.0.1:8000" : "";
}

/** Turn API-relative media paths into an absolute URL so `<img src>` works from the Vite dev origin. */
export function resolveMediaUrl(url: string | null | undefined): string | null {
  if (url == null || url === "") return null;
  if (/^https?:\/\//i.test(url)) return url;
  const base = apiBaseUrl();
  if (url.startsWith("/")) return `${base}${url}`;
  return `${base.replace(/\/$/, "")}/${url}`;
}

function extractHtmlTitle(html: string): string | null {
  const m = html.match(/<title>(.*?)<\/title>/i);
  return m?.[1]?.trim() ?? null;
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBaseUrl()}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
  });

  if (!res.ok) {
    const contentType = res.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const body: any = await res.json().catch(() => ({}));
      const detail = typeof body?.detail === "string" ? body.detail : res.statusText;
      throw new Error(detail);
    }

    const text = await res.text().catch(() => "");
    const title = extractHtmlTitle(text);
    throw new Error(title ?? res.statusText);
  }
  return (await res.json()) as T;
}

export async function getForm(
  inspectionId: string,
  uuid: string,
  language?: string | null
): Promise<GetFormResponse> {
  const q = language ? `?lang=${encodeURIComponent(language)}` : "";
  return await http<GetFormResponse>(
    `/api/public/inspections/${encodeURIComponent(inspectionId)}/links/${encodeURIComponent(uuid)}/${q}`
  );
}

export async function submitForm(
  inspectionId: string,
  uuid: string,
  answers: Record<string, unknown>,
  outputLanguage?: string
): Promise<SubmitResponse> {
  return await http<SubmitResponse>(
    `/api/public/inspections/${encodeURIComponent(inspectionId)}/links/${encodeURIComponent(uuid)}/submit/`,
    {
      method: "POST",
      body: JSON.stringify({ answers, output_language: outputLanguage })
    }
  );
}

export function submissionPdfUrl(inspectionId: string, linkUuid: string): string {
  return `${apiBaseUrl()}/api/public/inspections/${encodeURIComponent(inspectionId)}/links/${encodeURIComponent(linkUuid)}/pdf/`;
}

/** Fetches the respondent PDF (same rules as GET …/pdf/ on the server). */
export async function fetchSubmissionPdf(inspectionId: string, linkUuid: string): Promise<Blob> {
  const res = await fetch(submissionPdfUrl(inspectionId, linkUuid), { method: "GET" });
  if (!res.ok) {
    const contentType = res.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const body: Record<string, unknown> = (await res.json().catch(() => ({}))) as Record<string, unknown>;
      const detail = typeof body.detail === "string" ? body.detail : res.statusText;
      throw new Error(detail);
    }
    const text = await res.text().catch(() => "");
    throw new Error(text || res.statusText);
  }
  return await res.blob();
}


