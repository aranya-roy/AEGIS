"use client";
import { useAegis } from "@/hooks/useAegis";

export function ScamDNACard() {
  const dna = useAegis((s) => s.dna);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <h2 className="text-xs uppercase tracking-widest text-slate-400">Scam DNA match</h2>
      {dna ? (
        <>
          <div className="mt-3 text-4xl font-semibold text-sky-300 transition-all">
            {dna.matchPct}%
          </div>
          <div className="text-xs text-slate-400">structural similarity</div>
          <div className="mt-2 h-2 overflow-hidden rounded bg-slate-800">
            <div className="h-full bg-sky-400 transition-all duration-700" style={{ width: `${dna.matchPct}%` }} />
          </div>
          <p className="mt-3 text-sm text-slate-200">{dna.pattern}</p>
          <p className="text-xs text-slate-500">
            Seen across {dna.incidents} anonymized incidents (demo library)
          </p>
        </>
      ) : (
        <p className="mt-3 text-sm text-slate-500">Comparing against known workflows...</p>
      )}
    </div>
  );
}