"use client";
import { useAegis } from "@/hooks/useAegis";

export function PrivacyPanel() {
  const p = useAegis((s) => s.privacy);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <h2 className="text-xs uppercase tracking-widest text-slate-400">Privacy gate</h2>
      <dl className="mt-3 space-y-1 text-sm">
        <div className="flex justify-between"><dt className="text-slate-400">Personal entities found</dt><dd>{p.detected}</dd></div>
        <div className="flex justify-between"><dt className="text-slate-400">Removed</dt><dd>{p.removed}</dd></div>
        <div className="flex justify-between"><dt className="text-slate-400">Shown or sent on</dt><dd className="text-emerald-400">{p.transmitted}</dd></div>
      </dl>
      <p className="mt-3 text-[10px] text-slate-500">
        Redaction runs in this browser before anything is displayed. Nothing leaves this page.
      </p>
    </div>
  );
}