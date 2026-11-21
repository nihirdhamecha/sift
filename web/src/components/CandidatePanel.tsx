import { useEffect, useState, type ReactNode } from "react";
import type { ResultRow, Seen } from "../types";
import { VERDICT, answerWord, pct, years, type Verdict } from "../lang";
import { VerdictPill } from "./ui";

type Role = { title?: string | null; company?: string | null; location?: string | null; dates?: string | null;
  years?: number | null; internship?: boolean; career_break?: boolean; highlights?: string[] };
type Group = { name?: string | null; highlights?: string[] };

export default function CandidatePanel({ row, seen, verdict, threshold, reqs, who, onClose }: {
  row: ResultRow; seen: Seen | null; verdict: Verdict; threshold: number; reqs: { key: string; text: string }[];
  who?: { file: string; name: string }; onClose: () => void;
}) {
  const [raw, setRaw] = useState(false);
  const err = seen ? null : "This file couldn't be read, so there's nothing to show.";
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);

  const p = (seen?.payload ?? {}) as Record<string, unknown>;
  const exp = (p.experience ?? {}) as { total_years?: number | null; internship_years?: number | null; roles?: Role[] };
  const edu = (p.education ?? {}) as { details?: string[]; degrees?: { level: string; field: string | null }[] };
  const list = (k: string) => (Array.isArray(p[k]) ? (p[k] as unknown[]) : []);

  return (
    <>
      <div className="fixed inset-0 z-30 bg-zinc-900/30 backdrop-blur-sm" onClick={onClose} />
      <aside className="fixed inset-y-0 right-0 z-30 flex w-full max-w-xl flex-col border-l border-zinc-900/10 bg-[#FAFAF7] shadow-2xl" aria-label="Candidate details">
        <div className="flex items-start gap-3 border-b border-zinc-900/10 bg-white px-5 py-4">
          <div className="min-w-0 flex-1">
            <div className="text-lg font-semibold">{who ? (who.name || "Name not found") : <>Candidate <span className="font-mono">{row.id}</span></>}</div>
            {who && <div className="text-sm text-zinc-500">{who.file}</div>}
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <VerdictPill v={verdict} />
              {row.probability !== null && <span className="text-sm text-zinc-600 dark:text-zinc-600">{pct(row.probability)} match (cut-off {pct(threshold)})</span>}
            </div>
          </div>
          <button onClick={onClose} className="btn-ghost !px-3" aria-label="Close">Close</button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {(verdict === "review" || verdict === "error") && (
            <Box><p className="text-amber-800 dark:text-amber-300">{row.reason || VERDICT[verdict].help}</p></Box>
          )}

          {reqs.length > 0 && row.probability !== null && (
            <Box title="Why this score?">
              <ul className="space-y-2">
                {reqs.map((q) => {
                  const m = row.must_haves[q.key];
                  if (!m) return null;
                  const a = answerWord(m.prob);
                  return (
                    <li key={q.key} className="flex items-start gap-3">
                      <span className={`mt-0.5 w-20 shrink-0 rounded-md px-2 py-0.5 text-center text-xs font-semibold ${a.ok
                        ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-500"}`}>{a.word}</span>
                      <span>{q.text}</span>
                    </li>
                  );
                })}
              </ul>
            </Box>
          )}

          {seen?.warnings && seen.warnings.length > 0 && (
            <Box><div className="space-y-1 text-sm text-amber-800 dark:text-amber-300">
              <b>We may have missed part of this resume.</b>
              {seen.warnings.map((w) => <div key={w}>{w}</div>)}
              <div>Please check the original file.</div>
            </div></Box>
          )}

          {err && <p className="text-sm text-zinc-500">{err}</p>}

          {seen && (
            <>

              {(exp.roles?.length ?? 0) > 0 && (
                <Box title={`Experience${years(exp.total_years) ? ` · ${years(exp.total_years)}` : ""}${years(exp.internship_years) ? ` (+ ${years(exp.internship_years)} internships)` : ""}`}>
                  <ul className="space-y-4">
                    {exp.roles!.map((r, i) => (
                      <li key={i}>
                        <div className="font-medium">
                          {r.title || "Role"}{r.company && <span className="font-normal text-zinc-600 dark:text-zinc-600"> · {r.company}</span>}
                          {r.internship && <Tag>Internship</Tag>}{r.career_break && <Tag>Career break</Tag>}
                        </div>
                        <div className="text-sm text-zinc-500">{[r.dates, years(r.years), r.location].filter(Boolean).join(" · ")}</div>
                        {(r.highlights?.length ?? 0) > 0 && (
                          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm">{r.highlights!.map((h, j) => <li key={j}>{h}</li>)}</ul>
                        )}
                      </li>
                    ))}
                  </ul>
                </Box>
              )}

              {list("skills").length > 0 && (
                <Box title="Skills">
                  <div className="flex flex-wrap gap-1.5">
                    {(list("skills") as string[]).map((s) => <span key={s} className="rounded-md border border-zinc-900/10 bg-white px-2 py-0.5 text-sm text-zinc-800">{s}</span>)}
                  </div>
                </Box>
              )}

              {typeof p.summary === "string" && p.summary && <Box title="Summary"><p className="text-sm">{p.summary}</p></Box>}

              {((edu.details?.length ?? 0) > 0 || (edu.degrees?.length ?? 0) > 0) && (
                <Box title="Education">
                  <ul className="space-y-1 text-sm">
                    {(edu.details?.length ? edu.details : edu.degrees!.map((d) => `${d.level}${d.field ? `, ${d.field}` : ""}`)).map((d, i) => <li key={i}>{d}</li>)}
                  </ul>
                </Box>
              )}

              {list("projects").length > 0 && (
                <Box title="Projects">
                  <ul className="space-y-2 text-sm">
                    {(list("projects") as Group[]).map((g, i) => (
                      <li key={i}>{g.name && <div className="font-medium">{g.name}</div>}
                        {(g.highlights?.length ?? 0) > 0 && <ul className="list-disc pl-5">{g.highlights!.map((h, j) => <li key={j}>{h}</li>)}</ul>}</li>
                    ))}
                  </ul>
                </Box>
              )}

              {[["achievements", "Achievements"], ["certifications", "Certifications"], ["other", "Other details"]].map(([k, t]) =>
                list(k).length > 0 && (
                  <Box key={k} title={t}><ul className="list-disc space-y-1 pl-5 text-sm">{(list(k) as string[]).map((x, i) => <li key={i}>{x}</li>)}</ul></Box>
                ))}

              <button className="px-1 text-xs text-zinc-500 underline" onClick={() => setRaw(!raw)}>{raw ? "Hide" : "Show"} technical details</button>
              {raw && <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-white p-4 font-mono text-xs text-zinc-700">{JSON.stringify(seen.payload, null, 2)}</pre>}
            </>
          )}
        </div>
      </aside>
    </>
  );
}

function Box({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="card p-4">
      {title && <h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">{title}</h3>}
      {children}
    </section>
  );
}

function Tag({ children }: { children: ReactNode }) {
  return <span className="ml-2 rounded bg-zinc-100 px-1.5 py-0.5 align-middle text-xs font-normal text-zinc-600 dark:bg-zinc-800 dark:text-zinc-600">{children}</span>;
}
