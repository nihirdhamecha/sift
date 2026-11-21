import type { ReactNode } from "react";
import { VERDICT, type Verdict } from "../lang";

export function VerdictPill({ v, size = "sm" }: { v: Verdict; size?: "sm" | "lg" }) {
  return (
    <span title={VERDICT[v].help}
      className={`inline-block whitespace-nowrap rounded-full font-semibold ${size === "lg" ? "px-3 py-1 text-sm" : "px-2.5 py-0.5 text-xs"} ${VERDICT[v].cls}`}>
      {VERDICT[v].label}
    </span>
  );
}

export function Alert({ kind = "error", children, action, onClose }: {
  kind?: "error" | "info" | "warn" | "success"; children: ReactNode; action?: ReactNode; onClose?: () => void;
}) {
  const c = {
    error: "border-rose-200 bg-rose-50 text-rose-900",
    warn: "border-amber-200 bg-amber-50 text-amber-900",
    info: "border-zinc-900/10 bg-white text-zinc-800",
    success: "border-indigo-200 bg-indigo-50 text-indigo-900",
  }[kind];
  return (
    <div role={kind === "error" ? "alert" : "status"} className={`flex flex-wrap items-center gap-3 rounded-xl border px-4 py-3 text-sm ${c}`}>
      <div className="min-w-0 flex-1">{children}</div>
      {action}
      {onClose && <button onClick={onClose} aria-label="Dismiss" className="px-1 text-lg leading-none opacity-60 hover:opacity-100">×</button>}
    </div>
  );
}

export function Bar({ value, className = "" }: { value: number; className?: string }) {
  return (
    <div className={`h-2 w-full overflow-hidden rounded-full bg-zinc-900/[0.06] ${className}`}>
      <div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-indigo-300 transition-all duration-500" style={{ width: `${Math.round(value * 100)}%` }} />
    </div>
  );
}

export function Modal({ title, children, onClose, wide }: { title: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-zinc-900/30 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label={title}
      onKeyDown={(e) => e.key === "Escape" && onClose()} onClick={onClose}>
      <div className={`card max-h-[90vh] w-full overflow-y-auto p-6 shadow-2xl ${wide ? "max-w-2xl" : "max-w-md"}`} onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="-mr-1 px-1 text-2xl leading-none text-zinc-600 hover:text-zinc-900 dark:hover:text-zinc-900">×</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Step({ n, title, children }: { n: number; title: string; children?: ReactNode }) {
  return (
    <div className="flex gap-3">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-500/10 font-mono text-sm font-semibold text-indigo-600">{n}</span>
      <div><div className="font-medium">{title}</div>{children && <div className="text-sm text-zinc-500">{children}</div>}</div>
    </div>
  );
}

/** Page heading: indigo eyebrow, title with an indigo accent. */
export function PageTitle({ eyebrow, title, accent, sub, right }: {
  eyebrow: string; title: string; accent?: string; sub?: ReactNode; right?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <div className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">{eyebrow}</div>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
          {title}{accent && <> <span className="text-indigo-600">{accent}</span></>}
        </h1>
        {sub && <p className="mt-2 text-zinc-600">{sub}</p>}
      </div>
      {right && <div className="flex flex-wrap gap-2">{right}</div>}
    </div>
  );
}

/** Wordmark: lowercase "sift" in Inter Semibold. The dot of the i is the one signal in the pile. */
export function Logo({ small }: { small?: boolean }) {
  return (
    <span className={`inline-flex items-baseline font-semibold leading-none tracking-tight text-[#111111] ${small ? "text-xl" : "text-2xl"}`} role="img" aria-label="sift">
      <span aria-hidden>s</span>
      <span aria-hidden className="relative">
        {"\u0131"}
        <span className="absolute left-1/2 top-[-0.02em] h-[0.19em] w-[0.19em] -translate-x-1/2 rounded-full bg-indigo-600" />
      </span>
      <span aria-hidden>ft</span>
    </span>
  );
}

export const kb = (n: number) => (n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
