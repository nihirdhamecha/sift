import { useRef, useState } from "react";
import type { Job } from "../types";
import {
  DEFAULT_JOB, EMPTY_JOB, STRICTNESS, deleteSavedJob, jobProblems, newRequirement, parseJob, saveJob, savedJobs,
  strictnessOf, toQuestion, toRequirement,
} from "../job";
import { api, ApiError } from "../api";
import { Alert, PageTitle } from "./ui";

const EXAMPLES = ["At least 3 years of sales experience", "Has managed a team", "Knows Excel or Google Sheets", "Has a degree in finance or accounting"];

export default function JobSetup({ job, setJob, next }: { job: Job; setJob: (j: Job) => void; next: () => void }) {
  const [note, setNote] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [draft, setDraft] = useState("");
  const [saved, setSaved] = useState(savedJobs);
  const [more, setMore] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const jdRef = useRef<HTMLInputElement>(null);
  const [jdBusy, setJdBusy] = useState(false);
  const problems = jobProblems(job);
  const patch = (p: Partial<Job>) => setJob({ ...job, ...p });
  const level = strictnessOf(job.threshold);

  const addReq = (text = draft) => {
    if (text.trim().length < 3) return;
    patch({ must_haves: [...job.must_haves, newRequirement(text, job.must_haves)] });
    setDraft("");
  };
  const editReq = (i: number, text: string) =>
    patch({ must_haves: job.must_haves.map((m, k) => (k === i ? { ...m, question: toQuestion(text) } : m)) });
  const removeReq = (i: number) => patch({ must_haves: job.must_haves.filter((_, k) => k !== i) });

  const doSave = () => {
    const name = job.role.trim() || "Untitled job";
    saveJob(name, job); setSaved(savedJobs());
    setNote({ kind: "success", text: `Saved "${name}". You can pick it from "Saved jobs" next time.` });
  };
  const doLoad = (name: string) => {
    const j = saved[name];
    if (j) { setJob(parseJob(j)); setNote({ kind: "success", text: `Loaded "${name}".` }); }
  };
  const exportFile = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(job, null, 2)], { type: "application/json" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: `${(job.role || "job").replace(/[^\w-]+/g, "_")}.json` });
    a.click(); URL.revokeObjectURL(url);
  };
  const importFile = async (f?: File) => {
    if (!f) return;
    try { setJob(parseJob(JSON.parse(await f.text()))); setNote({ kind: "success", text: `Opened "${f.name}".` }); }
    catch { setNote({ kind: "error", text: "That file isn't a saved Sift job." }); }
    if (fileRef.current) fileRef.current.value = "";
  };

  const uploadJd = async (f?: File) => {
    if (!f) return;
    setJdBusy(true); setNote(null);
    try {
      const r = await api.jd(f);
      patch({ description: r.text });
      setNote({ kind: "success", text: `Added the job description from "${f.name}".${r.truncated ? " It was long, so only the first part was kept." : ""} Check it below.` });
    } catch (e) {
      setNote({ kind: "error", text: e instanceof ApiError ? e.message : "We couldn't read that file. Paste the job description instead." });
    } finally {
      setJdBusy(false);
      if (jdRef.current) jdRef.current.value = "";
    }
  };

  const savedNames = Object.keys(saved);

  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Step 1 of 3" title="Describe" accent="the job."  right={<>
          {savedNames.length > 0 && (
            <select className="input !w-auto" value="" onChange={(e) => doLoad(e.target.value)} aria-label="Saved jobs">
              <option value="" disabled>Saved jobs…</option>
              {savedNames.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          )}
          <button className="btn-ghost" onClick={() => { setJob(EMPTY_JOB); setNote(null); }}>Start a new job</button>
      </>} />
      {note && <Alert kind={note.kind} onClose={() => setNote(null)}>{note.text}</Alert>}

      <section className="card space-y-5 p-5 sm:p-6">
        <div>
          <label className="mb-1.5 block font-medium" htmlFor="role">Job title</label>
          <input id="role" className="input !text-base" value={job.role} onChange={(e) => patch({ role: e.target.value })} placeholder="For example: Sales Manager" />
        </div>
        <div>
          <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
            <label className="font-medium" htmlFor="desc">What does the job involve?</label>
            <input ref={jdRef} type="file" hidden accept=".pdf,.docx,.txt,.md,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(e) => uploadJd(e.target.files?.[0])} />
            <button type="button" className="btn-ghost !py-1.5 !text-sm" disabled={jdBusy} onClick={() => jdRef.current?.click()}>
              {jdBusy ? "Reading…" : "Upload JD (PDF, Word or text)"}
            </button>
          </div>
          <textarea id="desc" rows={6} className="input !text-base" value={job.description} onChange={(e) => patch({ description: e.target.value })}
            placeholder="Type or paste the job description, or upload it. For example: We're looking for a sales manager to lead a team of 6 in our retail business. They should have 3+ years in B2B sales and be comfortable with targets and reporting." />
        </div>
      </section>

      <section className="card space-y-4 p-5 sm:p-6">
        <div>
          <h2 className="font-medium">What must a candidate have?</h2>
        </div>
        <ul className="space-y-2">
          {job.must_haves.map((m, i) => (
            <li key={m.key} className="flex items-center gap-2">
              <span className="text-indigo-600" aria-hidden>✓</span>
              <input className="input" aria-label={`Requirement ${i + 1}`} value={toRequirement(m.question)} onChange={(e) => editReq(i, e.target.value)} />
              <button className="btn-ghost !px-3 shrink-0" onClick={() => removeReq(i)} aria-label={`Remove requirement ${i + 1}`}>Remove</button>
            </li>
          ))}
        </ul>
        {job.must_haves.length < 12 && (
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); addReq(); }}>
            <input className="input" value={draft} onChange={(e) => setDraft(e.target.value)} aria-label="New requirement"
              placeholder={job.must_haves.length ? "Add another requirement" : "For example: At least 3 years of sales experience"} />
            <button className="btn-primary shrink-0" disabled={draft.trim().length < 3}>Add</button>
          </form>
        )}
        {job.must_haves.length === 0 && (
          <div className="flex flex-wrap gap-2 text-sm">
            <span className="text-zinc-500">Ideas:</span>
            {EXAMPLES.map((x) => (
              <button key={x} onClick={() => addReq(x)} className="rounded-full border border-zinc-900/15 px-3 py-0.5 text-zinc-700 hover:border-indigo-400/50 hover:text-zinc-900">+ {x}</button>
            ))}
          </div>
        )}
      </section>

      <section className="card space-y-3 p-5 sm:p-6">
        <div>
          <h2 className="font-medium">How strict should the shortlist be?</h2>
        </div>
        <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label="Strictness">
          {STRICTNESS.map((s) => (
            <button key={s.id} role="radio" aria-checked={level === s.id} onClick={() => patch({ threshold: s.value })}
              className={`rounded-xl border p-3 text-left transition ${level === s.id
                ? "border-indigo-500/50 bg-indigo-500/10 text-zinc-900 ring-1 ring-indigo-500/20"
                : "border-zinc-900/10 text-zinc-700 hover:border-zinc-900/25 hover:bg-zinc-900/[0.04]"}`}>
              <div className="font-medium">{s.label}</div>
              <div className={`text-sm ${level === s.id ? "text-indigo-700/80" : "text-zinc-500"}`}>{s.hint}</div>
            </button>
          ))}
        </div>
        {level === "custom" && <p className="text-sm text-zinc-500">Custom level: {Math.round(job.threshold * 100)}% match needed.</p>}
      </section>

      <div>
        <button className="text-sm text-zinc-500 underline-offset-2 hover:underline" onClick={() => setMore(!more)} aria-expanded={more}>
          {more ? "Hide" : "Show"} more options
        </button>
        {more && (
          <div className="card mt-3 space-y-4 p-5 text-sm">
            <div>
              <label className="mb-1 block font-medium" htmlFor="thr">Exact match level: {Math.round(job.threshold * 100)}%</label>
              <input id="thr" type="range" min={0.3} max={0.9} step={0.05} value={job.threshold}
                onChange={(e) => patch({ threshold: parseFloat(e.target.value) })} className="w-full accent-indigo-600" />
              <p className="text-zinc-500">Candidates scoring at or above this go on the shortlist.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <input ref={fileRef} type="file" accept="application/json,.json" hidden onChange={(e) => importFile(e.target.files?.[0])} />
              <button className="btn-ghost" onClick={exportFile}>Download job as a file</button>
              <button className="btn-ghost" onClick={() => fileRef.current?.click()}>Open a job file</button>
              <button className="btn-ghost" onClick={() => setJob(DEFAULT_JOB)}>Use the example job</button>
              {savedNames.map((n) => (
                <button key={n} className="btn-ghost" onClick={() => { deleteSavedJob(n); setSaved(savedJobs()); }}>Delete saved "{n}"</button>
              ))}
            </div>
          </div>
        )}
      </div>

      {problems.length > 0 && <Alert kind="warn">{problems.map((p) => <div key={p}>{p}</div>)}</Alert>}
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <button className="btn-ghost" onClick={doSave} disabled={!job.role.trim()}>Save this job</button>
        <button className="btn-primary !px-6 !py-2.5 !text-base" disabled={problems.length > 0} onClick={next}>Next: add resumes →</button>
      </div>
    </div>
  );
}
