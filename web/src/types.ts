export interface MustHave { key: string; question: string }
export interface Job {
  role: string; description: string; shortlist_question: string;
  must_haves: MustHave[]; threshold: number;
}
export interface Health {
  mode: "live" | "mock"; has_key: boolean; model: string; redaction: "name" | "full"; max_mb: number; max_files: number;
}

/** One /api/score response. name_guess stays in React state and is only rendered after "Reveal names". */
export interface ScoreResult {
  id: string; mock: boolean; probability: number | null; decision: "GO" | "NO-GO" | "HUMAN REVIEW";
  must_haves: Record<string, { prob: number; pass: boolean }>; failed_must_haves: string[]; redacted: Record<string, unknown> | null;
  sections_found: string[]; warnings: string[]; redactions: Record<string, number>;
  name_guess: string; needs_human_review: boolean; reason: string | null;
}

export type ItemState = "queued" | "reading" | "waiting" | "done" | "review" | "error" | "rejected";
/** A file in the pile. Lives in React state only: never localStorage, never sent back to the server. */
export interface Item {
  key: string; file: File; state: ItemState; message: string | null; result: ScoreResult | null;
}

export interface ResultRow {
  id: string; probability: number | null; decision: "GO" | "NO-GO" | "HUMAN REVIEW" | "ERROR";
  must_haves: Record<string, { prob: number; pass: boolean }>; reason: string | null;
  profile?: { title: string | null; company: string | null; years: number | null } | null;
}
export interface Results {
  mock: boolean; status: string; threshold: number; role: string; must_haves: MustHave[];
  revealed: boolean; rows: ResultRow[]; names?: Record<string, { file: string; name: string }>;
}
export interface Seen {
  id: string; payload: Record<string, unknown>; redactions: Record<string, number>;
  sections_found: string[]; needs_human_review: boolean; warnings: string[];
}
