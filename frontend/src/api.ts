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

export class ApiHttpError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiHttpError";
    this.status = status;
    this.detail = detail;
  }
}

export function isApiHttpError(e: unknown): e is ApiHttpError {
  return e instanceof ApiHttpError;
}

async function readErrorDetail(res: Response): Promise<string> {
  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    const body: unknown = await res.json().catch(() => ({}));
    if (body && typeof body === "object" && "detail" in body) {
      const d = (body as { detail?: unknown }).detail;
      if (typeof d === "string" && d.trim()) return d.trim();
      if (Array.isArray(d) && d.length) {
        const parts = d
          .map((x) => {
            if (typeof x === "string") return x;
            if (x && typeof x === "object" && "string" in x && typeof (x as { string?: unknown }).string === "string") {
              return (x as { string: string }).string;
            }
            return null;
          })
          .filter((x): x is string => Boolean(x));
        if (parts.length) return parts.join("; ");
      }
    }
    return res.statusText || "Request failed";
  }

  const text = await res.text().catch(() => "");
  const title = extractHtmlTitle(text);
  return title ?? res.statusText ?? "Request failed";
}

async function httpJson<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${apiBaseUrl()}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {})
      },
      ...init
    });
  } catch (e: unknown) {
    if (e instanceof TypeError) {
      throw new TypeError("NETWORK");
    }
    throw e;
  }

  if (!res.ok) {
    const detail = await readErrorDetail(res);
    throw new ApiHttpError(res.status, detail);
  }
  return (await res.json()) as T;
}

export async function getForm(
  inspectionId: string,
  uuid: string,
  language?: string | null
): Promise<GetFormResponse> {
  const q = language ? `?lang=${encodeURIComponent(language)}` : "";
  return await httpJson<GetFormResponse>(
    `/api/public/inspections/${encodeURIComponent(inspectionId)}/links/${encodeURIComponent(uuid)}/${q}`
  );
}

export async function submitForm(
  inspectionId: string,
  uuid: string,
  answers: Record<string, unknown>,
  outputLanguage?: string
): Promise<SubmitResponse> {
  return await httpJson<SubmitResponse>(
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
  let res: Response;
  try {
    res = await fetch(submissionPdfUrl(inspectionId, linkUuid), { method: "GET" });
  } catch (e: unknown) {
    if (e instanceof TypeError) {
      throw new TypeError("NETWORK");
    }
    throw e;
  }
  if (!res.ok) {
    const detail = await readErrorDetail(res);
    throw new ApiHttpError(res.status, detail);
  }
  return await res.blob();
}
