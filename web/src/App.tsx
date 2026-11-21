import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, sampleFiles } from "./api";
import type { Health, Item, Job } from "./types";
import { DEFAULT_JOB, jobProblems, parseJob } from "./job";
import { buildResults, newItem, runQueue, seenOf } from "./queue";
import Header, { Tab } from "./components/Header";
import Landing from "./components/Landing";
import JobSetup from "./components/JobSetup";
import Upload from "./components/Upload";
import Results from "./components/Results";
import Settings from "./components/Settings";
import { Alert } from "./components/ui";

// localStorage holds only the job description and the welcome flag. Resumes, scores and the
// ID -> file -> name map live in React state and are gone when the tab closes.
const store = {
  get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k: string, v: string | null) => { try { if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch { /* ignore */ } },
};
function loadJob(): Job {
  try { const s = store.get("bf-job"); if (s) return parseJob(JSON.parse(s)); } catch { /* ignore */ }
  return DEFAULT_JOB;
}
const isPublic = typeof window !== "undefined" && !["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname);

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [bootErr, setBootErr] = useState<string | null>(null);
  const [welcome, setWelcome] = useState(() => !store.get("bf-welcomed"));
  const [settings, setSettings] = useState(false);
  const [tab, setTab] = useState<Tab>("job");
  const [job, setJob] = useState<Job>(loadJob);
  const [runJob, setRunJob] = useState<Job | null>(null);
  const [practice, setPractice] = useState(true);
  const [password, setPassword] = useState("");  // memory only
  const [items, setItems] = useState<Item[]>([]);
  const [running, setRunning] = useState(false);
  const [finished, setFinished] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [notes, setNotes] = useState<string[]>([]);
  const [demoBusy, setDemoBusy] = useState(false);
  const cancel = useRef(false);

  const problems = jobProblems(job);
  const liveOk = health?.mode === "live";
  const mock = practice || !liveOk;

  useEffect(() => {
    api.health().then(setHealth).catch((e: ApiError) => setBootErr(e.message));
    return () => { cancel.current = true; };
  }, []);
  useEffect(() => { store.set("bf-job", JSON.stringify(job)); }, [job]);

  const say = useCallback((m: string) => setErrors((c) => (c.includes(m) ? c : [...c, m])), []);
  const leaveWelcome = () => { setWelcome(false); store.set("bf-welcomed", "1"); };
  const patch = useCallback((key: string, p: Partial<Item>) =>
    setItems((cur) => cur.map((i) => (i.key === key ? { ...i, ...p } : i))), []);

  // --- add / remove
  const add = (files: File[], replace = false) => {
    if (!health) return;
    const room = health.max_files - (replace ? 0 : items.filter((i) => i.state !== "rejected").length);
    const next = files.map((f) => newItem(f, health.max_mb));
    const ok = next.filter((i) => i.state !== "rejected");
    const over = Math.max(0, ok.length - room);
    const keep = over ? [...next.filter((i) => i.state === "rejected"), ...ok.slice(0, room)] : next;
    const msgs: string[] = [];
    const bad = keep.filter((i) => i.state === "rejected").length;
    if (bad) msgs.push(`${bad} file${bad > 1 ? "s" : ""} can't be checked (see the list below).`);
    if (over) msgs.push(`${over} file${over > 1 ? "s were" : " was"} skipped: the limit is ${health.max_files} resumes per run.`);
    setNotes(msgs);
    setItems((cur) => (replace ? keep : [...cur, ...keep]));
    setFinished(false); setRevealed(false);
  };
  const remove = (key: string) => setItems((cur) => cur.filter((i) => i.key !== key));

  const demo = async () => {
    setDemoBusy(true);
    try {
      const files = await sampleFiles();
      setJob(DEFAULT_JOB); add(files, true); setTab("upload"); leaveWelcome();
      setNotes(["3 sample resumes and an example job were added. Click the button below to check them."]);
    } catch (e) { leaveWelcome(); say((e as Error).message); } finally { setDemoBusy(false); }
  };

  // --- run: one PDF per request, PARALLEL at a time
  const start = async (retry: boolean) => {
    setErrors([]); setNotes([]);
    const snap = retry && runJob ? runJob : job;
    const targets = items.filter((i) => (retry ? i.state === "error" || i.state === "queued" : i.state !== "rejected"));
    if (!targets.length) return;
    if (!retry) {
      setRevealed(false);
      setItems((cur) => cur.map((i) => (i.state === "rejected" ? i : { ...i, state: "queued", message: null, result: null })));
    }
    setRunJob(snap); setRunning(true); setFinished(false); cancel.current = false;
    const fatal = await runQueue(targets, snap, mock, password, patch, () => cancel.current);
    setRunning(false); setFinished(true);
    if (fatal) {
      if (fatal.code === "bad_password") setSettings(true);
      say(fatal.message);
    } else {
      setTab("results");
    }
  };

  const results = useMemo(() => (runJob ? buildResults(items, runJob, revealed, finished && !running) : null), [items, runJob, revealed, finished, running]);
  const hasResults = !!results && results.rows.length > 0;

  if (!health) {
    return <div className="mx-auto max-w-lg p-10 text-center text-zinc-500">{bootErr ? <Alert>{bootErr}</Alert> : "Starting Sift…"}</div>;
  }
  const showMock = tab === "results" && results ? results.mock : mock;

  const banners = (
    <>
      {isPublic && (
        <div className="relative z-40 bg-[#111111] px-4 py-1.5 text-center text-sm font-medium text-white" role="note">
          Demo only. Don't upload real resumes.
        </div>
      )}
      {showMock && (
        <div className="relative z-30 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-sm text-amber-900" role="status">
          <span><b>MOCK SCORES - NOT REAL.</b> Practice mode makes up the scores.</span>
          {liveOk && (
            <button className="rounded-full border border-amber-300 bg-white px-3 py-0.5 text-amber-900 hover:bg-amber-100"
              onClick={() => (password ? setPractice(false) : setSettings(true))}>
              {password ? "Use real scores" : "Enter password for real scores"}
            </button>
          )}
        </div>
      )}
    </>
  );

  if (welcome) {
    return (
      <>
        {isPublic && banners}
        <Landing onStart={() => { leaveWelcome(); setTab("job"); window.scrollTo(0, 0); }}
          onDemo={async () => { await demo(); window.scrollTo(0, 0); }} busy={demoBusy} />
      </>
    );
  }

  return (
    <div className="relative min-h-screen overflow-x-hidden">
      <div className="bg-grid pointer-events-none absolute inset-x-0 top-0 h-[520px]" aria-hidden />
      <div className="pointer-events-none absolute left-1/2 top-[-260px] h-[480px] w-[900px] -translate-x-1/2 rounded-full bg-indigo-300/25 blur-[140px]" aria-hidden />
      {banners}
      <Header tab={tab} setTab={(t) => { leaveWelcome(); setTab(t); }} onHelp={() => { setWelcome(true); window.scrollTo(0, 0); }} onSettings={() => setSettings(true)}
        disabled={{ results: !hasResults }} />
      <main className="relative mx-auto max-w-5xl space-y-6 px-5 py-10">
        {errors.map((m, i) => (
          <Alert key={m} onClose={() => setErrors((c) => c.filter((_, k) => k !== i))}>{m}</Alert>
        ))}
        {tab === "job" && <JobSetup job={job} setJob={setJob} next={() => setTab("upload")} />}
        {tab === "upload" && (
          <Upload items={items} health={health} busy={running} practice={mock} canRun={problems.length === 0}
            onAdd={add} onRemove={remove} onRun={() => start(false)} onRetry={() => start(true)}
            onSamples={demo} onBack={() => setTab("job")} notes={notes} clearNotes={() => setNotes([])} />
        )}
        {tab === "results" && results && (
          <Results data={results} seen={(id) => seenOf(items, id)} onReveal={async () => setRevealed(true)} onRerun={() => setTab("job")} />
        )}
      </main>
      {settings && (
        <Settings health={health} practice={mock} setPractice={setPractice} password={password}
          setPassword={setPassword} onClose={() => setSettings(false)} />
      )}
    </div>
  );
}
