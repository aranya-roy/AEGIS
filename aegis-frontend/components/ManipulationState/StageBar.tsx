"use client";
import { useAegis } from "@/hooks/useAegis";
import type { Stage } from "@/types/events";

const STAGES: Stage[] = ["TRUST", "AUTHORITY", "URGENCY", "ISOLATION", "COMPLIANCE", "MONEY_MOVEMENT"];

export function StageBar() {
  const stage = useAegis((s) => s.stage);
  const current = stage ? STAGES.indexOf(stage.stage) : -1;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <h2 className="text-xs uppercase tracking-widest text-slate-400">Manipulation stage</h2>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {STAGES.map((st, i) => (
          <span
            key={st}
            className={`rounded px-2 py-0.5 text-[11px] ${
              i === current
                ? "bg-amber-500 font-semibold text-slate-950"
                : i < current
                ? "bg-slate-600 text-slate-100"
                : "bg-slate-800 text-slate-500"
            }`}
          >
            {st.replace("_", " ")}
          </span>
        ))}
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded bg-slate-800">
        <div
          className="h-full bg-amber-500 transition-all duration-700"
          style={{ width: `${Math.round((stage?.progress ?? 0) * 100)}%` }}
        />
      </div>
      <p className="mt-2 min-h-[2.5rem] text-xs text-slate-300">
        {stage?.reason ?? "Waiting for interaction..."}
      </p>
      <p className="text-[10px] text-slate-500">
        Based on observable communication signals, not the user&apos;s mind.
      </p>
    </div>
  );
}