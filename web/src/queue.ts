import { api, ApiError } from "./api";
import type { Item, Job, ResultRow, Results, ScoreResult, Seen } from "./types";

export const PARALLEL = 5;
export const MAX_TRIES = 4;
const STOP_CODES = new Set(["missing_key", "auth", "bad_job"]);

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Plain-language reasons for files rejected in the browser, before anything is uploaded. */
export function checkFile(f: File, maxMb: number): string | null {
  if (!/\.pdf$/i.test(f.name) && f.type !== "application/pdf") return "Not a PDF file.";
  if (f.size > maxMb * 1024 * 1024) return `Bigger than ${maxMb} MB. Save a smaller PDF and add it again.`;
  return null;
}

let seq = 0;
export const newItem = (file: File, maxMb: number): Item => {
  const bad = checkFile(file, maxMb);
  return { key: `f${++seq}`, file, state: bad ? "rejected" : "queued", message: bad, result: null };
};

type Patch = (key: string, p: Partial<Item>) => void;

/**
 * Score items one PDF per request, at most PARALLEL at a time. A 429 waits for the server's
 * retry-after hint, then doubles, up to MAX_TRIES. Errors that will hit every file (missing or
 * broken key) stop the whole run and are returned so the page can explain them once.
 */
export async function runQueue(items: Item[], job: Job, patch: Patch,
  cancelled: () => boolean): Promise<ApiError | null> {
  const todo = [...items];
  let fatal: ApiError | null = null;

  const one = async (it: Item) => {
    for (let attempt = 1; attempt <= MAX_TRIES; attempt++) {
      if (fatal || cancelled()) { patch(it.key, { state: "queued", message: null }); return; }
      patch(it.key, { state: "reading", message: null });
      try {
        const r: ScoreResult = await api.score(it.file, job);
        patch(it.key, { state: r.needs_human_review ? "review" : "done", result: r, message: r.reason });
        return;
      } catch (e) {
        const ae = e instanceof ApiError ? e : new ApiError("error", "Something went wrong.", 0);
        if (STOP_CODES.has(ae.code)) { fatal = fatal ?? ae; patch(it.key, { state: "queued", message: null }); return; }
        if (ae.status === 413 || ae.status === 415) { patch(it.key, { state: "rejected", message: ae.message }); return; }
        const retryable = ae.status === 429 || ae.status === 0 || ae.status >= 502;
        if (!retryable || attempt === MAX_TRIES) {
          patch(it.key, { state: "error", message: ae.status === 429 ? "The AI is still busy (code 429). Click Try again in a minute." : ae.message });
          return;
        }
        const wait = ae.status === 429 ? (ae.retryAfter ?? 20) * 1000 * 2 ** (attempt - 1) : 2000 * attempt;
        patch(it.key, { state: "waiting", message: ae.status === 429 ? `AI busy, retrying in ${Math.round(wait / 1000)}s` : "Retrying…" });
        await sleep(Math.min(wait, 90_000));
      }
    }
  };

  const worker = async () => { for (let it = todo.shift(); it; it = todo.shift()) await one(it); };
  await Promise.all(Array.from({ length: Math.min(PARALLEL, todo.length) }, worker));
  return fatal;
}

// ------------------------------------------------------------------ results from browser state
function profile(payload: Record<string, unknown> | null): ResultRow["profile"] {
  if (!payload) return null;
  const exp = (payload.experience ?? {}) as { total_years?: number | null; roles?: { title?: string; company?: string; career_break?: boolean }[] };
  const top = (exp.roles ?? []).find((r) => r.title && !r.career_break);
  return { title: top?.title ?? null, company: top?.company ?? null, years: exp.total_years ?? null };
}

export function toRow(it: Item): ResultRow | null {
  const r = it.result;
  if (r) return { id: r.id, probability: r.probability, decision: r.decision, must_haves: r.must_haves, reason: r.reason, profile: profile(r.redacted) };
  if (it.state === "error") return { id: it.key, probability: null, decision: "ERROR", must_haves: {}, reason: it.message, profile: null };
  return null;
}

/** Build the results view. Names are only included once the recruiter has chosen to reveal them. */
export function buildResults(items: Item[], job: Job, revealed: boolean, done: boolean): Results {
  const scored = items.filter((i) => i.result || i.state === "error");
  const out: Results = {
    mock: scored.some((i) => i.result?.mock), status: done ? "done" : "running", threshold: job.threshold,
    role: job.role, must_haves: job.must_haves, revealed,
    rows: scored.map(toRow).filter((r): r is ResultRow => r !== null),
  };
  if (revealed) {
    out.names = Object.fromEntries(scored.map((i) => [i.result?.id ?? i.key, { file: i.file.name, name: i.result?.name_guess ?? "" }]));
  }
  return out;
}

export function seenOf(items: Item[], id: string): Seen | null {
  const r = items.find((i) => i.result?.id === id)?.result;
  if (!r || !r.redacted) return null;
  return { id: r.id, payload: r.redacted, redactions: r.redactions, sections_found: r.sections_found,
    needs_human_review: r.needs_human_review, warnings: r.warnings };
}

// ------------------------------------------------------------------ CSV, built in the browser
const safe = (v: unknown) => {
  const s = v == null ? "" : String(v);
  const g = /^[=+\-@\t\r]/.test(s) ? `'${s}` : s;
  return /[",\n]/.test(g) ? `"${g.replace(/"/g, '""')}"` : g;
};

export function exportCsv(data: Results) {
  const keys = data.must_haves.map((m) => m.key);
  const rows = [...data.rows].sort((a, b) => (b.probability ?? -1) - (a.probability ?? -1));
  const head = [...(data.revealed ? ["candidate_name", "file"] : []), "id", "decision", "probability", ...keys, "note"];
  const lines = rows.map((r) => {
    const who = data.names?.[r.id];
    return [
      ...(data.revealed ? [who?.name ?? "", who?.file ?? ""] : []), r.id, r.decision, r.probability ?? "",
      ...keys.map((k) => (k in r.must_haves ? (r.must_haves[k].pass ? "yes" : "no") : "")),
      r.reason ?? (data.mock ? "MOCK SCORES - NOT REAL" : ""),
    ].map(safe).join(",");
  });
  const url = URL.createObjectURL(new Blob([[head.join(","), ...lines].join("\n") + "\n"], { type: "text/csv" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: data.revealed ? "shortlist.csv" : "shortlist-blind.csv" });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
