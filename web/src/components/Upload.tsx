import { useRef, useState } from "react";
import type { Health, Item } from "../types";
import { Alert, Bar, PageTitle, kb } from "./ui";

const STATE_LABEL: Record<string, string> = {
  queued: "Waiting", reading: "Reading and checking…", waiting: "Waiting for the AI", done: "Done ✓",
  review: "Please read this one yourself", error: "Couldn't check", rejected: "Can't be checked",
};
const TONE: Record<string, string> = {
  error: "text-rose-600", rejected: "text-rose-600", review: "text-amber-700", done: "text-green-700",
  waiting: "text-amber-700", reading: "text-indigo-600", queued: "text-zinc-500",
};

export default function Upload({ items, health, busy, practice, canRun, onAdd, onRemove, onRun, onRetry, onSamples, onBack, notes, clearNotes }: {
  items: Item[]; health: Health; busy: boolean; practice: boolean; canRun: boolean;
  onAdd: (f: File[]) => void; onRemove: (key: string) => void; onRun: () => void; onRetry: () => void; onSamples: () => void; onBack: () => void;
  notes: string[]; clearNotes: () => void;
}) {
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const take = (list: FileList | null) => { if (list?.length) onAdd(Array.from(list)); };
  const usable = items.filter((i) => i.state !== "rejected");
  const n = usable.length;
  const finished = usable.filter((i) => ["done", "review", "error"].includes(i.state)).length;
  const failed = usable.filter((i) => i.state === "error").length;

  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Step 2 of 3" title="Add" accent="resumes." />

      {!busy && (
        <div onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); take(e.dataTransfer.files); }}
          onClick={() => input.current?.click()} role="button" tabIndex={0}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
          className={`flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-14 text-center transition ${
            over ? "border-indigo-500/60 bg-indigo-500/10" : "border-zinc-900/15 bg-white/70 hover:border-indigo-400/40 hover:bg-white"}`}>
          <input ref={input} type="file" accept="application/pdf,.pdf" multiple hidden onChange={(e) => { take(e.target.files); e.target.value = ""; }} />
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-indigo-600" aria-hidden>
            <path d="M12 16V4m0 0-4 4m4-4 4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <p className="mt-3 text-lg font-medium">Drop the pile here.</p>
          <p className="text-zinc-500">PDFs up to {health.max_mb} MB, {health.max_files} per run · or <span className="font-medium text-indigo-600 underline underline-offset-4">click to choose files</span></p>
        </div>
      )}

      {items.length === 0 && !busy && (
        <p className="text-center text-sm text-zinc-500">
          No resumes handy? <button className="font-medium underline" onClick={onSamples}>Add 3 sample resumes</button> to try it out.
        </p>
      )}

      {notes.length > 0 && <Alert kind="warn" onClose={clearNotes}>{notes.map((x, i) => <div key={i}>{x}</div>)}</Alert>}

      {busy && (
        <div className="card space-y-3 p-5">
          <div className="flex items-baseline justify-between">
            <span className="font-medium">Sifting through the pile…</span>
            <span className="text-zinc-500">{finished} of {n}</span>
          </div>
          <Bar value={n ? finished / n : 0} />
        </div>
      )}

      {items.length > 0 && (
        <section className="card">
          <div className="flex items-center justify-between border-b border-zinc-900/10 px-4 py-3">
            <span className="font-medium">{n} resume{n === 1 ? "" : "s"} added</span>
            <span className="text-sm text-zinc-500">Names stay hidden until you reveal them.</span>
          </div>
          <ul className="max-h-80 divide-y divide-zinc-900/5 overflow-y-auto">
            {items.map((it, idx) => (
              <li key={it.key} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                <span className="font-medium">
                  {it.result ? <>Candidate <span className="font-mono">{it.result.id}</span></> : <>Resume {idx + 1}</>}
                </span>
                <span className="text-zinc-600">{kb(it.file.size)}</span>
                <span className={`flex-1 text-right ${TONE[it.state]}`}>
                  {it.state === "error" || it.state === "rejected" || it.state === "waiting" ? it.message ?? STATE_LABEL[it.state] : STATE_LABEL[it.state]}
                </span>
                {!busy && <button className="text-zinc-500 hover:text-rose-600" onClick={() => onRemove(it.key)} aria-label={`Remove resume ${idx + 1}`}>Remove</button>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {!canRun && <Alert kind="warn">Finish describing the job first. <button className="font-medium underline" onClick={onBack}>Go back</button></Alert>}
      {practice && n > 0 && !busy && <p className="text-right text-sm text-amber-700">Practice mode is on: scores will be made up.</p>}

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
        <button className="btn-ghost" onClick={onBack} disabled={busy}>← Back to job</button>
        <div className="flex flex-col gap-2 sm:flex-row">
          {!busy && failed > 0 && <button className="btn-ghost" onClick={onRetry}>Try again for {failed} resume{failed === 1 ? "" : "s"}</button>}
          <button className="btn-primary !px-6 !py-2.5 !text-base" disabled={!n || busy || !canRun} onClick={onRun}>
            {busy ? "Sifting…" : n ? `Sift ${n} resume${n === 1 ? "" : "s"} →` : "Add resumes to continue"}
          </button>
        </div>
      </div>
    </div>
  );
}
