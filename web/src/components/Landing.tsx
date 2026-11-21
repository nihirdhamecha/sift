import { Logo } from "./ui";

const d = (ms: number) => ({ animationDelay: `${ms}ms` });

export default function Landing({ onStart, onDemo, busy }: { onStart: () => void; onDemo: () => void; busy: boolean }) {
  return (
    <div className="flex min-h-screen flex-col bg-[#FAFAF7] text-[#111111] antialiased">
      <header className="sticky top-0 z-30 border-b border-zinc-900/5 bg-[#FAFAF7]/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4">
          <Logo />
          <button onClick={onStart} className="rounded-full bg-[#111111] px-4 py-2 text-sm font-semibold text-white transition hover:bg-zinc-700">
            Sift resumes
          </button>
        </div>
      </header>

      <section className="relative flex flex-1 flex-col overflow-hidden">
        <div className="bg-grid pointer-events-none absolute inset-0" aria-hidden />
        <div className="pointer-events-none absolute left-1/2 top-[-20%] h-[600px] w-[900px] -translate-x-1/2 rounded-full bg-indigo-300/30 blur-[140px]" aria-hidden />

        <div className="relative mx-auto flex max-w-3xl flex-1 flex-col items-center justify-center px-5 pb-16 pt-16 text-center md:pt-24">
          <div className="bf-fade-up inline-flex items-center gap-2 rounded-full border border-zinc-900/10 bg-white/70 px-3 py-1 text-xs font-medium text-zinc-700" style={d(0)}>
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-500" />
            Built on Jev by TypeSafe
          </div>
          <h1 className="bf-fade-up mt-7 text-balance text-[2.6rem] font-semibold leading-[1.04] tracking-tight sm:text-6xl lg:text-7xl" style={d(80)}>
            Find the signal <span className="text-indigo-600">in the pile.</span>
          </h1>
          <p className="bf-fade-up mt-6 max-w-xl text-balance text-lg leading-relaxed text-zinc-600" style={d(160)}>
            Sift ranks every resume against your job in seconds. It only answers yes-or-no questions
            about each one, so it can't invent skills or experience.
          </p>
          <div className="bf-fade-up mt-10 flex w-full flex-col justify-center gap-3 sm:w-auto sm:flex-row" style={d(240)}>
            <button onClick={onStart}
              className="group rounded-full bg-[#111111] px-7 py-3.5 text-base font-semibold text-white shadow-lg shadow-zinc-900/20 transition hover:bg-zinc-700">
              Sift resumes <span className="inline-block transition group-hover:translate-x-1">→</span>
            </button>
            <button onClick={onDemo} disabled={busy}
              className="rounded-full border border-zinc-900/15 bg-white/70 px-7 py-3.5 text-base font-medium text-zinc-800 transition hover:border-zinc-900/30 hover:bg-white disabled:opacity-50">
              {busy ? "Loading samples…" : "Try with sample resumes"}
            </button>
          </div>
        </div>

        <div className="bf-fade-up relative mx-auto w-full max-w-6xl px-5 pb-16" style={d(320)}>
          <ol className="grid gap-px overflow-hidden rounded-2xl border border-zinc-900/10 bg-[#111111]/[0.06] sm:grid-cols-3">
            {[["Describe the job", "Title, description and must-haves."],
              ["Add resumes", "Drop in up to 100 PDFs."],
              ["Review the shortlist", "See who matches and why."]].map(([t, x], i) => (
              <li key={t} className="flex items-start gap-4 bg-white p-5">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-sm font-semibold text-indigo-600">{i + 1}</span>
                <div><div className="font-semibold">{t}</div><div className="text-sm text-zinc-500">{x}</div></div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="border-t border-zinc-900/5 bg-white">
        <div className="mx-auto max-w-4xl px-5 py-16 md:py-24">
          <h2 className="text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
            Why not your ATS, <span className="text-indigo-600">or ChatGPT?</span>
          </h2>
          <p className="mt-3 text-lg text-zinc-600">ATS tools match keywords. LLMs write opinions. Sift makes a call you can measure.</p>

          <div className="mt-10 overflow-x-auto rounded-2xl border border-zinc-900/10">
            <table className="w-full min-w-[640px] border-collapse text-left text-sm">
              <thead>
                <tr className="bg-[#FAFAF7]">
                  <th className="p-4" />
                  <th className="p-4 font-medium text-zinc-500">Keyword ATS</th>
                  <th className="p-4 font-medium text-zinc-500">LLM screening</th>
                  <th className="bg-indigo-50 p-4 font-semibold text-indigo-700">Sift</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["Reads for meaning", "No", "Yes", "Yes"],
                  ["Output", "Keyword match", "A paragraph", "GO / NO-GO + probability"],
                  ["Makes things up?", "No", "Yes, it can", "No"],
                  ["Same result every time?", "Yes", "Not always", "Yes"],
                  ["Sees name, college, age?", "Usually", "Usually", "Never"],
                  ["Fast and cheap at volume?", "Yes", "No", "Yes"],
                ].map(([label, a, b, c]) => (
                  <tr key={label} className="border-t border-zinc-900/10">
                    <th scope="row" className="p-4 font-medium">{label}</th>
                    <td className="p-4 text-zinc-500">{a}</td>
                    <td className="p-4 text-zinc-500">{b}</td>
                    <td className="bg-indigo-50/60 p-4 font-semibold text-zinc-900">{c}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-10 rounded-2xl bg-[#111111] p-7 text-white sm:p-9">
            <h3 className="text-2xl font-semibold tracking-tight">It can't make things up.</h3>
            <p className="mt-2 max-w-2xl text-lg leading-relaxed text-zinc-300">
              Sift doesn't write answers, so it can't invent a skill or a reason. It answers fixed questions
              with a probability, and a recruiter makes the final call.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
