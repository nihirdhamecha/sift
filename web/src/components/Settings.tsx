import { useState } from "react";
import type { Health } from "../types";
import { Modal } from "./ui";

export default function Settings({ health, practice, setPractice, password, setPassword, onClose }: {
  health: Health; practice: boolean; setPractice: (p: boolean) => void;
  password: string; setPassword: (p: string) => void; onClose: () => void;
}) {
  const [draft, setDraft] = useState(password);
  const live = health.mode === "live";

  return (
    <Modal title="Settings" onClose={onClose}>
      <div className="space-y-6">
        <section>
          <h3 className="font-medium">Real scores</h3>
          {live ? (
            <>
              <p className="mt-1 text-sm text-zinc-500">Enter the demo password you were given to score resumes with the real AI. It's kept only in this tab.</p>
              <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); setPassword(draft.trim()); setPractice(false); onClose(); }}>
                <input type="password" className="input" placeholder="Demo password" value={draft} onChange={(e) => setDraft(e.target.value)}
                  aria-label="Demo password" autoComplete="off" />
                <button className="btn-primary shrink-0" disabled={!draft.trim()}>Use real scores</button>
              </form>
            </>
          ) : (
            <p className="mt-1 text-sm text-zinc-500">
              {health.demo_mode ? "This copy of Sift is a demo, so scores are always made up."
                : "The AI isn't set up on this server yet, so scores are made up. Whoever runs Sift needs to set TYPESAFE_API_KEY and DEMO_PASSWORD."}
            </p>
          )}
        </section>

        <section>
          <label className="flex items-start gap-3">
            <input type="checkbox" className="mt-1 h-4 w-4 accent-indigo-600" checked={practice} disabled={!live || !password}
              onChange={(e) => setPractice(e.target.checked)} />
            <span>
              <span className="font-medium">Practice mode</span>
              <span className="block text-sm text-zinc-500">Uses made-up scores so you can try things out. {(!live || !password) && "Always on until real scores are available."}</span>
            </span>
          </label>
        </section>

        <section className="space-y-2 border-t border-zinc-900/10 pt-4 text-sm text-zinc-600">
          <h3 className="font-medium text-zinc-900">Privacy</h3>
          <p>
            {health.redaction === "full"
              ? "The AI never sees names, contact details, colleges, cities, dates, gender or personal details."
              : "The AI never sees the candidate's name, email, phone or profile links. The rest of the resume is sent as written."}
          </p>
          <p>Each resume is checked on its own and nothing is stored on the server. Names stay in this browser tab and disappear when you close it.</p>
        </section>
      </div>
    </Modal>
  );
}
