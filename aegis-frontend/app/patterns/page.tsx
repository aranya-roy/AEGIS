"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { incidents, newIncident, STEP_LABEL, STEP_COLOR, type Incident } from "@/demo/incidents";
import { averagePairSimilarity, predictNext } from "@/services/patterns";

function Row({ inc, predicted }: { inc: Incident; predicted?: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <div className="flex items-baseline justify-between">
        <span className="font-medium">{inc.label}</span>
        <span className="text-xs text-slate-500">{inc.surface}</span>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {inc.steps.map((st, i) => (
          <span key={st + i} className="flex items-center gap-2">
            <span className={`rounded border px-2 py-1 text-xs ${STEP_COLOR[st]}`}>{STEP_LABEL[st]}</span>
            {(i < inc.steps.length - 1 || predicted) && <span className="text-slate-600">→</span>}
          </span>
        ))}
        {predicted && (
          <span className="rounded border-2 border-dashed border-amber-400 px-2 py-1 text-xs text-amber-300">
            🔮 {predicted}
          </span>
        )}
      </div>
    </div>
  );
}

export default function Patterns() {
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing) return;
    if (step >= 5) { setPlaying(false); return; }
    const t = setTimeout(() => setStep((s) => s + 1), 2200);
    return () => clearTimeout(t);
  }, [playing, step]);

  const sim = Math.round(averagePairSimilarity(incidents) * 100);
  const pred = predictNext(newIncident.steps, incidents);

  return (
    <main className="mx-auto min-h-screen max-w-4xl space-y-4 bg-slate-950 p-4 text-slate-100">
      <header className="flex items-center justify-between">
        <h1 className="font-semibold tracking-wide">AEGIS · Pattern engine</h1>
        <div className="flex items-center gap-3">
          <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">← Live call</Link>
          <button className="rounded bg-emerald-600 px-3 py-1" onClick={() => { setStep(1); setPlaying(true); }}>
            Start
          </button>
          <button className="rounded bg-slate-700 px-3 py-1" onClick={() => { setStep(0); setPlaying(false); }}>
            Reset
          </button>
        </div>
      </header>

      <p className="text-sm text-slate-400">
        Different brands, languages and channels. Same underlying workflow. Anonymized demo incidents.
      </p>

      {incidents.slice(0, Math.min(step, 3)).map((inc) => <Row key={inc.id} inc={inc} />)}

      {step >= 4 && (
        <div className="rounded-xl border border-sky-500/40 bg-sky-500/10 p-5 text-center">
          <div className="text-xs uppercase tracking-widest text-sky-300">Same underlying workflow</div>
          <div className="mt-1 text-5xl font-semibold text-sky-200">{sim}%</div>
          <div className="text-sm text-slate-300">structural similarity across incidents A, B and C</div>
          <div className="mt-1 text-[11px] text-slate-500">
            Computed from step order (longest common subsequence), ignoring brand and channel names.
          </div>
        </div>
      )}

      {step >= 5 && (
        <>
          <Row inc={newIncident} predicted={pred ? STEP_LABEL[pred.next] : undefined} />
          {pred && (
            <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-200">
              AEGIS recognizes the pattern <b>before the money step</b>. Likely next:{" "}
              <b>{STEP_LABEL[pred.next]}</b>, matched in {pred.votes} of {pred.total} known incidents. Early warning would trigger now.
            </div>
          )}
        </>
      )}
    </main>
  );
}