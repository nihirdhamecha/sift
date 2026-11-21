import type { Health, Job, ScoreResult } from "./types";

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number, public retryAfter?: number) { super(message); }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { credentials: "omit", ...init });
  } catch {
    throw new ApiError("network", "Couldn't reach Sift. Check your internet connection and try again.", 0);
  }
  if (!res.ok) {
    let body: { code?: string; detail?: string; retry_after?: number } = {};
    try { body = await res.json(); } catch { /* not json */ }
    const ra = body.retry_after ?? (Number(res.headers.get("Retry-After")) || undefined);
    const fallback = res.status === 413 ? "This file is too large." : `Request failed (${res.status})`;
    throw new ApiError(body.code ?? (res.status === 429 ? "rate_limited" : "error"), body.detail ?? fallback, res.status, ra);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => call<Health>("/api/health"),
  /** One resume per request. The filename is not sent: the server only sees the PDF bytes. */
  score: (file: File, job: Job, mock: boolean, password: string) => {
    const fd = new FormData();
    fd.append("file", new Blob([file], { type: "application/pdf" }), "resume.pdf");
    fd.append("job", JSON.stringify(job));
    fd.append("mock", String(mock));
    const headers: Record<string, string> = password ? { "X-Sift-Password": password } : {};
    return call<ScoreResult>("/api/score", { method: "POST", body: fd, headers });
  },
};

/** The three fictional sample resumes, bundled as static files. */
export async function sampleFiles(): Promise<File[]> {
  const names = ["sample_ananya.pdf", "sample_imran.pdf", "sample_rohit.pdf"];
  return Promise.all(names.map(async (n) => {
    const r = await fetch(`/samples/${n}`);
    if (!r.ok) throw new ApiError("samples", "Couldn't load the sample resumes.", r.status);
    return new File([await r.blob()], n, { type: "application/pdf" });
  }));
}
