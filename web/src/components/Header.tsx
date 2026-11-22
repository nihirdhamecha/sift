import { Logo } from "./ui";

export type Tab = "job" | "upload" | "results";

const STEPS: { id: Tab; n: number; label: string; short: string }[] = [
  { id: "job", n: 1, label: "Describe the job", short: "Job" },
  { id: "upload", n: 2, label: "Add resumes", short: "Resumes" },
  { id: "results", n: 3, label: "See shortlist", short: "Shortlist" },
];

export default function Header({ tab, setTab, disabled, onHelp, onSettings }: {
  tab: Tab; setTab: (t: Tab) => void; disabled: Partial<Record<Tab, boolean>>; onHelp: () => void; onSettings: () => void;
}) {
  return (
    <header className="sticky top-0 z-20 border-b border-zinc-900/5 bg-[#FAFAF7]/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3">
        <button onClick={onHelp} className="flex items-center" aria-label="sift home"><Logo /></button>
        <nav className="order-3 flex w-full gap-1 sm:order-none sm:w-auto sm:flex-1" aria-label="Steps">
          {STEPS.map((s) => {
            const active = tab === s.id;
            return (
              <button key={s.id} disabled={disabled[s.id]} onClick={() => setTab(s.id)} aria-current={active ? "step" : undefined}
                className={`flex flex-1 items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40 sm:flex-none ${
                  active ? "bg-zinc-900/[0.06] text-zinc-900 ring-1 ring-zinc-900/10" : "text-zinc-600 hover:bg-zinc-900/[0.04] hover:text-zinc-900"}`}>
                <span className={`flex h-5 w-5 items-center justify-center rounded-full text-xs font-semibold ${active ? "bg-indigo-500 text-white" : "bg-zinc-900/[0.06]"}`}>{s.n}</span>
                <span className="truncate sm:hidden">{s.short}</span>
                <span className="hidden truncate sm:inline">{s.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-1">
          <button onClick={onHelp} className="btn !text-zinc-600 hover:!text-zinc-900">Help</button>
          <button onClick={onSettings} className="btn !text-zinc-600 hover:!text-zinc-900">Privacy</button>
        </div>
      </div>
    </header>
  );
}
