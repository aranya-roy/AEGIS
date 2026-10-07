import { create } from "zustand";
import { AegisEvent, Stage, RiskLevel } from "@/types/events";
import { sanitize } from "@/services/sanitize";

type State = {
  transcript: { speaker: string; text: string }[];
  signals: { label: string; severity: string; evidence: string }[];
  nodes: { id: string; label: string; parent?: string; predicted?: boolean }[];
  stage?: { stage: Stage; progress: number; reason: string };
  dna?: { matchPct: number; pattern: string; incidents: number };
  path?: { next: string; confidence: number; evidence: string[] };
  risk: { level: RiskLevel; drivers: string[] };
  privacy: { detected: number; removed: number; transmitted: number };
  pause?: { reasons: string[] };
  running: boolean;
  apply: (e: AegisEvent) => void;
  play: (events: AegisEvent[], speed?: number) => void;
  reset: () => void;
};

const initial = {
  transcript: [],
  signals: [],
  nodes: [],
  stage: undefined,
  dna: undefined,
  path: undefined,
  pause: undefined,
  risk: { level: "NORMAL" as RiskLevel, drivers: [] },
  privacy: { detected: 0, removed: 0, transmitted: 0 },
  running: false,
};

let timers: ReturnType<typeof setTimeout>[] = [];

export const useAegis = create<State>((set, get) => ({
  ...initial,
  apply: (e) =>
    set((s) => {
      switch (e.type) {
        case "transcript": {
          const r = sanitize(e.text);
          return {
            transcript: [...s.transcript, { speaker: e.speaker, text: r.text }],
            privacy: {
              detected: s.privacy.detected + r.count,
              removed: s.privacy.removed + r.count,
              transmitted: 0,
            },
          };
        }
        case "signal": return { signals: [...s.signals, e] };
        case "graph_node": return { nodes: [...s.nodes, e] };
        case "stage": return { stage: e };
        case "scam_dna": return { dna: e };
        case "shadowpath": return { path: e };
        case "risk": return { risk: { level: e.level, drivers: e.drivers } };
        case "privacy": return { privacy: e };
        case "reality_pause": return { pause: e };
      }
    }),
  play: (events, speed = 1) => {
    get().reset();
    set({ running: true });
    timers = events.map((e) => setTimeout(() => get().apply(e), e.at / speed));
  },
  reset: () => {
    timers.forEach(clearTimeout);
    timers = [];
    set({ ...initial });
  },
}));