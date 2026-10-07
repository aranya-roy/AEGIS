"use client";
import { useState } from "react";
import Link from "next/link";
import { useAegis } from "@/hooks/useAegis";
import { bankScam } from "@/demo/bankScam";
import { RealityPause } from "@/components/RealityPause/RealityPause";
import { AttackGraph } from "@/components/AttackGraph/AttackGraph";
import { RiskBanner } from "@/components/RiskEngine/RiskBanner";
import { StageBar } from "@/components/ManipulationState/StageBar";
import { ScamDNACard } from "@/components/ScamDNA/ScamDNACard";
import { ShadowPathCard } from "@/components/ShadowPath/ShadowPathCard";
import { PrivacyPanel } from "@/components/PrivacyGate/PrivacyPanel";

export default function Home() {
  const s = useAegis();
  const [speed, setSpeed] = useState(1);

  return (
    <main className="flex min-h-screen flex-col gap-4 bg-slate-950 p-4 text-slate-100">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <h1 className="font-semibold tracking-wide">AEGIS</h1>
          <span className="flex items-center gap-1 text-xs text-slate-400">
            <span className={`h-2 w-2 rounded-full ${s.running ? "animate-pulse bg-red-500" : "bg-slate-600"}`} />
            {s.running ? "SIMULATED CALL IN PROGRESS" : "IDLE"}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/patterns" className="text-sm text-slate-400 hover:text-slate-200">Pattern engine →</Link>
          <select
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
            className="rounded bg-slate-800 px-2 py-1 text-sm"
          >
            <option value={1}>1x</option>
            <option value={1.5}>1.5x</option>
            <option value={2}>2x</option>
          </select>
          <button className="rounded bg-emerald-600 px-3 py-1" onClick={() => s.play(bankScam, speed)}>Start demo</button>
          <button className="rounded bg-slate-700 px-3 py-1" onClick={s.reset}>Reset</button>
        </div>
      </header>

      <RiskBanner />

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_2fr]">
        <div className="max-h-[520px] space-y-4 overflow-auto rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div>
            <h2 className="mb-2 text-xs uppercase tracking-widest text-slate-400">Live interaction (redacted)</h2>
            {s.transcript.length === 0 && <p className="text-sm text-slate-500">Press Start demo.</p>}
            {s.transcript.map((t, i) => (
              <p key={i} className="mb-2 text-sm text-slate-200">
                <span className="text-slate-500">{t.speaker}:</span> {t.text}
              </p>
            ))}
          </div>
          <div>
            <h2 className="mb-2 text-xs uppercase tracking-widest text-slate-400">Signals</h2>
            {s.signals.map((g, i) => (
              <div key={i} className="mb-2">
                <p className={`text-sm ${g.severity === "critical" ? "text-red-400" : "text-amber-400"}`}>
                  {g.severity === "critical" ? "⚠" : "✓"} {g.label}
                </p>
                <p className="text-xs text-slate-500">{g.evidence}</p>
              </div>
            ))}
          </div>
        </div>
        <AttackGraph />
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StageBar />
        <ScamDNACard />
        <ShadowPathCard />
        <PrivacyPanel />
      </section>

      {s.pause && <RealityPause reasons={s.pause.reasons} onClose={s.reset} />}
    </main>
  );
}