"use client";
import { useAegis } from "@/hooks/useAegis";

const STYLE = {
  NORMAL: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  WATCH: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  INTERVENE: "border-orange-500/50 bg-orange-500/10 text-orange-300",
  CRITICAL: "border-red-500/60 bg-red-500/15 text-red-300",
} as const;

const MESSAGE = {
  NORMAL: "No scam pattern detected.",
  WATCH: "Some early warning signs. AEGIS is watching.",
  INTERVENE: "Pattern is escalating. Intervention is being prepared.",
  CRITICAL: "A dangerous action is close. Interrupting now.",
} as const;

export function RiskBanner() {
  const risk = useAegis((s) => s.risk);
  return (
    <div className={`rounded-xl border px-4 py-3 transition-colors duration-500 ${STYLE[risk.level]}`}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="text-xs uppercase tracking-widest opacity-70">Risk engine</span>
        <span className="text-lg font-semibold">{risk.level}</span>
        <span className="text-sm opacity-90">{MESSAGE[risk.level]}</span>
      </div>
      {risk.drivers.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2 text-xs">
          <span className="opacity-70">Why:</span>
          {risk.drivers.map((d) => (
            <span key={d} className="rounded-full border border-current/30 px-2 py-0.5">
              {d}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}