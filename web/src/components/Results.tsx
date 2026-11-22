import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type { ResultRow, Results as R, Seen } from "../types";
import { exportCsv } from "../queue";
import { toRequirement } from "../job";
import { VERDICT, pct, verdictOf, years, type Verdict } from "../lang";
import { Modal, PageTitle, VerdictPill } from "./ui";
import CandidatePanel from "./CandidatePanel";

type Filter = "all" | Verdict;
const ORDER: Verdict[] = ["shortlist", "borderline", "no", "review", "error"];

export default function Results({ data, seen, onReveal, onRerun }: {
  data: R; seen: (id: string) => Seen | null; onReveal: () => Promise<void>; onRerun: () => void;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const [best, setBest] = useState(true);
  const [open, setOpen] = useState<ResultRow | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [ready, setReady] = useState(false);
  const reqs = useMemo(() => data.must_haves.map((m) => ({ key: m.key, text: toRequirement(m.question) })), [data]);
  const v = (r: ResultRow) => verdictOf(r, data.threshold);

  // Signature moment: when names are revealed, the cards fall back into ranked order and the
  // shortlisted ones rise to the top.
  const [settling, setSettling] = useState(false);
  const wasRevealed = useRef(data.revealed);
  useEffect(() => {
    if (data.revealed && !wasRevealed.current) {
      setFilter("all"); setBest(true); setSettling(true);
      const t = setTimeout(() => setSettling(false), 2200);
      wasRevealed.current = true;
      return () => clearTimeout(t);
    }
    wasRevealed.current = data.revealed;
  }, [data.revealed]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: data.rows.length };
    data.rows.forEach((r) => { const k = v(r); c[k] = (c[k] ?? 0) + 1; });
    return c;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  const rows = useMemo(() => {
    const f = data.rows.filter((r) => filter === "all" || v(r) === filter);
    return [...f].sort((a, b) => {
      const x = a.probability ?? -1, y = b.probability ?? -1;
      return best ? y - x : x - y;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, filter, best]);

  const tiles: { id: Filter; label: string; tone: string }[] = [
    { id: "shortlist", label: "Shortlisted", tone: "text-green-600" },
    { id: "borderline", label: "Borderline", tone: "text-indigo-600" },
    { id: "no", label: "Not this time", tone: "text-gray-400" },
    { id: "review", label: "Read yourself", tone: "text-amber-700 dark:text-amber-400" },
  ];
  if (counts.error) tiles.push({ id: "error", label: "Not scored", tone: "text-rose-700 dark:text-rose-400" });

  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Step 3 of 3" title="Shortlist for" accent={`${data.role}.`}
        sub="Click a candidate to see why."
        right={<>
          <button className="btn-ghost" onClick={onRerun}>Edit job</button>
          <button className="btn-ghost" onClick={() => exportCsv(data)}>Download as spreadsheet</button>
          {!data.revealed && <button className="btn-primary" disabled={data.status !== "done"} onClick={() => setConfirm(true)}>Reveal names</button>}
        </>} />

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {tiles.map((t) => (
          <button key={t.id} onClick={() => setFilter(filter === t.id ? "all" : t.id)} aria-pressed={filter === t.id}
            className={`card p-4 text-left transition hover:border-zinc-900/25 ${filter === t.id ? "!border-indigo-500/50 !bg-indigo-50 ring-1 ring-indigo-500/20" : ""}`}>
            <div className={`text-3xl font-semibold ${t.tone}`}>{counts[t.id] ?? 0}</div>
            <div className="text-sm text-zinc-600 dark:text-zinc-600">{t.label}</div>
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="text-zinc-500">
          {filter === "all" ? `Showing all ${data.rows.length} candidates` : `Showing ${VERDICT[filter as Verdict].label.toLowerCase()} (${rows.length}).`}{" "}
          {filter !== "all" && <button className="font-medium underline" onClick={() => setFilter("all")}>Show all</button>}
        </span>
        <label className="flex items-center gap-2 text-zinc-600 dark:text-zinc-600">
          Sort:
          <select className="input !w-auto !py-1" value={best ? "best" : "low"} onChange={(e) => setBest(e.target.value === "best")}>
            <option value="best">Best match first</option>
            <option value="low">Lowest match first</option>
          </select>
        </label>
      </div>

      <ul className="space-y-2">
        {rows.map((r, i) => {
          const verdict = v(r);
          const rise = verdict === "shortlist";
          // a loose pile: small, deterministic offsets per card
          const jitter = ((parseInt(r.id.replace(/\D/g, ""), 10) || i) % 7) - 3;
          const settle: CSSProperties | undefined = settling ? ({
            "--sx": `${jitter * 4}px`, "--sy": rise ? `${90 + i * 18}px` : `${14 + i * 6}px`, "--sr": `${jitter * 0.6}deg`,
            animationDelay: `${rise ? i * 90 : 250 + i * 60}ms`,
          } as CSSProperties) : undefined;
          const met = reqs.filter((q) => r.must_haves[q.key]?.pass).length;
          const who = data.names?.[r.id];
          const p = r.profile;
          return (
            <li key={r.id} className={settling ? (rise ? "sift-rise relative z-10 rounded-2xl" : "sift-settle") : ""} style={settle}>
              <button onClick={() => setOpen(r)}
                className="card flex w-full flex-wrap items-center gap-x-5 gap-y-2 p-4 text-left transition hover:border-indigo-400/30 hover:bg-zinc-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-300">
                <div className="min-w-0 flex-1 basis-56">
                  <div className="font-medium">
                    {who ? <span className="animate-reveal">{who.name || "Name not found"}</span> : <>Candidate <span className="font-mono">{r.id}</span></>}
                  </div>
                  <div className="truncate text-sm text-zinc-500">
                    {verdict === "review" || verdict === "error" ? r.reason
                      : [p?.title && (p.company ? `${p.title} at ${p.company}` : p.title), years(p?.years) && `${years(p?.years)} experience`].filter(Boolean).join(" · ") || "No work experience found"}
                    {who && <span className="animate-reveal"> · {who.file}</span>}
                  </div>
                  {verdict === "borderline" && (
                    <div className="mt-1 text-sm text-indigo-700">
                      Not shown: {reqs.filter((q) => r.must_haves[q.key] && !r.must_haves[q.key].pass).map((q) => q.text).join(", ")}
                    </div>
                  )}
                </div>
                {r.probability !== null && (
                  <div className="w-36">
                    <div className="flex justify-between text-sm"><span className="text-zinc-500">Match</span><span className="font-semibold">{pct(r.probability)}</span></div>
                    <div className="relative mt-1 h-2 rounded-full bg-zinc-900/[0.06]">
                      <div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-indigo-300" style={{ width: pct(r.probability) }} />
                      <div className="absolute -top-0.5 h-3 w-0.5 rounded bg-rose-500" style={{ left: pct(data.threshold) }} title="Shortlist cut-off" />
                    </div>
                  </div>
                )}
                {reqs.length > 0 && r.probability !== null && (
                  <div className="w-32 text-sm" title={reqs.map((q) => `${r.must_haves[q.key]?.pass ? "✓" : "✗"} ${q.text}`).join("\n")}>
                    <div className="text-zinc-500">Requirements</div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{met} of {reqs.length}</span>
                      <span className="flex gap-0.5" aria-hidden>
                        {reqs.map((q) => <span key={q.key} className={`h-2 w-2 rounded-full ${r.must_haves[q.key]?.pass ? "bg-green-600" : "bg-gray-400/40"}`} />)}
                      </span>
                    </div>
                  </div>
                )}
                <div className="sm:w-28 sm:text-right"><VerdictPill v={verdict} /></div>
              </button>
            </li>
          );
        })}
        {rows.length === 0 && <li className="card p-10 text-center text-zinc-500">No candidates here.</li>}
      </ul>

      {open && <CandidatePanel row={open} seen={seen(open.id)} verdict={v(open)} threshold={data.threshold} reqs={reqs}
        who={data.revealed ? data.names?.[open.id] : undefined} onClose={() => setOpen(null)} />}

      {confirm && (
        <Modal title="Reveal names?" onClose={() => { setConfirm(false); setReady(false); }}>
          <p className="text-zinc-600 dark:text-zinc-600">
            Names are hidden so you first judge candidates on their experience and skills, not on who they are.
            Once revealed, they stay visible until you close this tab.
          </p>
          <label className="mt-5 flex items-start gap-3">
            <input type="checkbox" className="mt-1 h-4 w-4" checked={ready} onChange={(e) => setReady(e.target.checked)} />
            <span>I've gone through the list and I'm ready to see names.</span>
          </label>
          <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button className="btn-ghost" onClick={() => { setConfirm(false); setReady(false); }}>Not yet</button>
            <button className="btn-primary" disabled={!ready} onClick={async () => { setConfirm(false); await onReveal(); }}>Reveal names</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

export { ORDER };
