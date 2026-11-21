import type { ResultRow } from "./types";

// Jev's scores wobble by about ±2 points on identical input, so anything within 5 points
// of the cut-off is shown as "Borderline" rather than a confident yes or no.
export const BORDER = 0.05;

export type Verdict = "shortlist" | "borderline" | "no" | "review" | "error";

export function verdictOf(r: ResultRow, threshold: number): Verdict {
  if (r.decision === "ERROR") return "error";
  if (r.decision === "REVIEW" || r.probability === null) return "review";
  if (Math.abs(r.probability - threshold) <= BORDER) return "borderline";
  return r.probability >= threshold ? "shortlist" : "no";
}

export const VERDICT: Record<Verdict, { label: string; cls: string; help: string }> = {
  shortlist: { label: "Shortlisted", cls: "bg-green-50 text-green-700 ring-1 ring-green-600/25", help: "A good match for this job." },
  borderline: { label: "Borderline", cls: "bg-indigo-50 text-indigo-700 ring-1 ring-indigo-600/20", help: "Close to the cut-off. Worth a quick look." },
  no: { label: "Not this time", cls: "bg-gray-100 text-gray-500 ring-1 ring-gray-400/40", help: "Doesn't match this job well." },
  review: { label: "Read yourself", cls: "bg-amber-50 text-amber-700 ring-1 ring-amber-600/20", help: "We couldn't read this file properly." },
  error: { label: "Not scored", cls: "bg-rose-50 text-rose-700 ring-1 ring-rose-600/20", help: "Something went wrong. Try again." },
};

export function answerWord(p: number): { word: string; ok: boolean } {
  if (p >= 0.75) return { word: "Yes", ok: true };
  if (p >= 0.5) return { word: "Probably", ok: true };
  if (p >= 0.25) return { word: "Unclear", ok: false };
  return { word: "No", ok: false };
}

export const pct = (p: number) => `${Math.round(p * 100)}%`;
export const years = (y: number | null | undefined) =>
  y == null ? null : y < 1 ? `${Math.round(y * 12)} months` : `${y.toFixed(1).replace(/\.0$/, "")} years`;
