"use client";
import { useAegis } from "@/hooks/useAegis";

export function ShadowPathCard() {
  const path = useAegis((s) => s.path);
  const signals = useAegis((s) => s.signals);
  const current = signals.length ? signals[signals.length - 1].label : null;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <h2 className="text-xs uppercase tracking-widest text-slate-400">ShadowPath</h2>
      {path ? (
        <>
          <div className="mt-3 text-xs text-slate-400">Current</div>
          <div className="text-sm text-slate-200">{current}</div>
          <div className="my-1 text-slate-600">↓</div>
          <div className="text-xs text-amber-400">🔮 Likely next step</div>
          <div className="text-base font-semibold text-amber-300">{path.next}</div>
          <div className="text-xs text-slate-400">Confidence: {path.confidence}%</div>
          <ul className="mt-2 space-y-0.5 text-xs text-slate-400">
            {path.evidence.map((e) => (
              <li key={e}>• {e}</li>
            ))}
          </ul>
        </>
      ) : (
        <p className="mt-3 text-sm text-slate-500">Not enough evidence to predict yet...</p>
      )}
    </div>
  );
}