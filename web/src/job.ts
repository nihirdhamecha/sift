import type { Job, MustHave } from "./types";

// ---------------------------------------------------------------- requirements
// Recruiters type a plain requirement ("2+ years of product management"). The AI needs it
// phrased as a yes/no question about the resume, so we wrap and unwrap it here.
const Q_PREFIX = "Based only on `resume`, does the candidate meet this requirement: ";
const Q_SUFFIX = "? Count it as met if the resume shows it, even when it is described in different words or without the same abbreviation.";
const OLD_PREFIX = "Based only on `resume`, does the candidate meet this requirement for the role in `job`: ";
// The server also spells out abbreviations (D2C, B2B, SaaS...) before Jev reads them.

export function toQuestion(requirement: string): string {
  const r = requirement.trim().replace(/[?.]+$/, "");
  return `${Q_PREFIX}${r}${Q_SUFFIX}`;
}

export function toRequirement(question: string): string {
  if (question.startsWith(Q_PREFIX)) return question.slice(Q_PREFIX.length).replace(Q_SUFFIX, "").replace(/\?$/, "");
  if (question.startsWith(OLD_PREFIX)) return question.slice(OLD_PREFIX.length).replace(/\?$/, "");
  // Older saved jobs used "Does `resume` show ...?"
  return question
    .replace(/`/g, "")
    .replace(/^does resume show (that )?(the candidate )?/i, "")
    .replace(/,? as asked for in job/i, "")
    .replace(/\?$/, "")
    .replace(/^./, (c) => c.toUpperCase());
}

export function slug(q: string, taken: Set<string>): string {
  const base = q.toLowerCase().replace(/`[^`]*`/g, " ").replace(/[^a-z0-9 ]/g, " ").split(/\s+/)
    .filter((w) => w.length > 2 && !["does", "the", "show", "candidate", "for", "has", "with", "based", "only", "meet", "this", "requirement", "role"].includes(w))
    .slice(0, 3).join("_") || "req";
  let k = /^[a-z]/.test(base) ? base : `r_${base}`;
  k = k.slice(0, 36);
  let n = 2, out = k;
  while (taken.has(out) || out === "shortlist") out = `${k}_${n++}`;
  return out;
}

export function newRequirement(text: string, existing: MustHave[]): MustHave {
  return { key: slug(text, new Set(existing.map((m) => m.key))), question: toQuestion(text) };
}

// ---------------------------------------------------------------- strictness
export const STRICTNESS = [
  { id: "relaxed", label: "Relaxed", value: 0.55, hint: "More candidates make the shortlist" },
  { id: "balanced", label: "Balanced", value: 0.7, hint: "Recommended for most roles" },
  { id: "strict", label: "Strict", value: 0.85, hint: "Only very strong matches" },
] as const;

export const strictnessOf = (t: number) => STRICTNESS.find((s) => Math.abs(s.value - t) < 0.001)?.id ?? "custom";

// ---------------------------------------------------------------- defaults + storage
export const DEFAULT_JOB: Job = {
  role: "Product Manager",
  description:
    "Product Manager for a consumer app. Owns a product area end to end: discovery, writing specs, working with engineering and design, launching to production, and tracking impact with data. Needs 2-5 years of product management experience, hands-on use of data (SQL or analytics tools) to make decisions, and experience shipping features to real users.",
  shortlist_question:
    "Based only on `resume`, should this candidate be shortlisted for a first interview for the role described in `job`?",
  must_haves: [
    { key: "shipped_to_production", question: toQuestion("Has launched a product or feature to real users") },
    { key: "relevant_experience", question: toQuestion("At least 2 years of product management experience") },
    { key: "data_driven", question: toQuestion("Uses data, metrics or experiments to make product decisions") },
  ],
  threshold: 0.7,
};

export const EMPTY_JOB: Job = { ...DEFAULT_JOB, role: "", description: "", must_haves: [] };

/** Accepts the same shape as config/job.json (extra fields like _note are ignored). */
export function parseJob(raw: unknown): Job {
  const j = raw as Partial<Job>;
  if (!j || typeof j.role !== "string" || typeof j.description !== "string") throw new Error("This file isn't a saved job.");
  const taken = new Set<string>();
  const must = (j.must_haves ?? []).map((m) => {
    const key = m.key && /^[a-z][a-z0-9_]{0,39}$/.test(m.key) && m.key !== "shortlist" && !taken.has(m.key) ? m.key : slug(m.question, taken);
    taken.add(key);
    return { key, question: String(m.question) };
  });
  const t = Number(j.threshold ?? 0.7);
  return {
    role: j.role, description: j.description,
    shortlist_question: j.shortlist_question || DEFAULT_JOB.shortlist_question,
    must_haves: must, threshold: Math.min(0.9, Math.max(0.3, isNaN(t) ? 0.7 : t)),
  };
}

export function jobProblems(j: Job): string[] {
  const p: string[] = [];
  if (!j.role.trim()) p.push("Add the job title.");
  if (j.description.trim().length < 30) p.push("Add a short job description (a few sentences is enough).");
  if (j.must_haves.some((m) => toRequirement(m.question).trim().length < 3)) p.push("One of the requirements is empty.");
  return p;
}

const SAVED = "bf-saved-jobs";
export function savedJobs(): Record<string, Job> {
  try { return JSON.parse(localStorage.getItem(SAVED) || "{}"); } catch { return {}; }
}
export function saveJob(name: string, job: Job) {
  try { localStorage.setItem(SAVED, JSON.stringify({ ...savedJobs(), [name]: job })); } catch { /* ignore */ }
}
export function deleteSavedJob(name: string) {
  const all = savedJobs(); delete all[name];
  try { localStorage.setItem(SAVED, JSON.stringify(all)); } catch { /* ignore */ }
}
