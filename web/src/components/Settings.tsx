import type { Health } from "../types";
import { Modal } from "./ui";

export default function Settings({ health, onClose }: { health: Health; onClose: () => void }) {
  return (
    <Modal title="Privacy" onClose={onClose}>
      <div className="space-y-3 text-sm text-zinc-600">
        <p>
          {health.redaction === "full"
            ? "The AI never sees names, contact details, colleges, cities, dates, gender or personal details."
            : "The AI never sees the candidate's name, email, phone or profile links. The rest of the resume is sent as written."}
        </p>
        <p>Each resume is checked on its own and nothing is stored on the server. Names stay in this browser tab and disappear when you close it.</p>
        <p>Scores come from Jev ({health.model}). It answers fixed yes-or-no questions with a probability, so it can't invent skills or experience. A person should make the final call.</p>
      </div>
    </Modal>
  );
}
