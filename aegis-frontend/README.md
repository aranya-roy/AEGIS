# AEGIS

**Adaptive Engine for Graph-based Intelligence & Scam-interruption**
RAKSHAM – AI Cybersecurity Hackathon, IIT Delhi · Problem Statement 02: AI-Driven Scam Pattern Recognition

> Scammers don't steal money first. They steal the decision.

AEGIS doesn't just say "this is a scam". It shows how an attack is progressing, what the attacker will probably do next, and when to interrupt the user.

---

## Repositories

| Repo | Purpose (proposed) | Owner role |
|---|---|---|
| **aegis-core** | Detection logic: privacy filter, semantic extraction, manipulation state machine, Scam DNA, ShadowPath | #1 AI/ML |
| **aegis-realtime** | Streaming layer: ingests a call/chat stream and delivers ordered events to the frontend (e.g. WebSocket) | #2 Real-Time Systems |
| **aegis-backend** | APIs, causal action graph, risk engine, cross-incident pattern data | #3 Backend/Graph |
| **aegis-frontend** | Dashboard, Reality Pause, pattern-engine view, demo mode (this repo) | Frontend + Demo Lead |
| **aegis-data** | Demo scenarios, anonymized incident library, labeled test sets for privacy and detection | shared |
| **aegis-docs** | Architecture notes, event schema, demo script, slides, setup guides | shared |

> Responsibilities above are proposed from repo names and team roles. If a repo's real scope differs, update this table in all six READMEs.

---

## How the pieces fit

```text
 aegis-data ──(scenarios, incidents, test sets)──┐
                                                 ▼
 Call / Chat / Message ─► aegis-realtime ─► aegis-core ─► aegis-backend
                           (stream)         (detect)       (graph, risk,
                                                            patterns)
                                                 │
                                                 ▼
                                   AegisEvent stream (see contract)
                                                 │
                                                 ▼
                                          aegis-frontend
                                   (dashboard, Reality Pause)
```

Pipeline in plain words: stream in → remove personal data → extract meaning → rebuild the attack workflow → track stage, match Scam DNA, predict next step → compute explainable risk → intervene with Reality Pause.

Population loop: many anonymized incidents → behavioral fingerprints → clustering → emerging scam workflow → better future detection.

---

## Shared event contract

Every repo that produces data for the UI must emit these events. This is the single interface between the backend side and the frontend. Change it only by agreement, and record changes in **aegis-docs**.

```ts
type Stage = "TRUST" | "AUTHORITY" | "URGENCY" | "ISOLATION" | "COMPLIANCE" | "MONEY_MOVEMENT";
type RiskLevel = "NORMAL" | "WATCH" | "INTERVENE" | "CRITICAL";

type AegisEvent =
  | { type: "transcript"; at: number; speaker: "caller" | "user"; text: string }
  | { type: "signal"; at: number; label: string; severity: "info" | "warn" | "critical"; evidence: string }
  | { type: "stage"; at: number; stage: Stage; progress: number; reason: string }
  | { type: "graph_node"; at: number; id: string; label: string; parent?: string; predicted?: boolean }
  | { type: "scam_dna"; at: number; matchPct: number; pattern: string; incidents: number }
  | { type: "shadowpath"; at: number; next: string; confidence: number; evidence: string[] }
  | { type: "risk"; at: number; level: RiskLevel; drivers: string[] }
  | { type: "privacy"; at: number; detected: number; removed: number; transmitted: number }
  | { type: "reality_pause"; at: number; reasons: string[] };
```

Conventions:
- `at` is milliseconds from the start of the interaction.
- `progress` is 0 to 1. `confidence` and `matchPct` are 0 to 100.
- `risk` events must include `drivers` (why the level changed). No bare scores.
- Use only the four risk levels.
- `transcript.text` must already be sanitized. Never send raw PII to the UI.
- Stage names describe observable communication signals, not the user's psychological state.

Who emits what:

| Event | Expected producer |
|---|---|
| `transcript`, `privacy` | aegis-core (privacy filter) |
| `signal`, `stage`, `scam_dna`, `shadowpath` | aegis-core |
| `graph_node`, `risk`, `reality_pause` | aegis-backend |
| delivery, ordering, reconnects | aegis-realtime |

---

## Current status

Honest snapshot, so nobody over-claims in the demo:

| Part | Status |
|---|---|
| **aegis-frontend** | Working. Browser-only demo with scripted Scene 1 and computed Scene 2 |
| aegis-core | Not yet integrated with the frontend |
| aegis-realtime | Not yet integrated with the frontend |
| aegis-backend | Not yet integrated with the frontend |
| aegis-data | Demo incidents currently live in `aegis-frontend/demo/` |
| aegis-docs | Update as repos land |

The frontend runs standalone, so the demo works even if no other repo is ready. Update this table as integrations land.

---

## aegis-frontend (this repo)

### What's built

**Scene 1: `/` (live dashboard)**
- Simulated call with a redacted live transcript
- Semantic signals with evidence
- Attack graph that grows node by node (React Flow), with a dashed predicted node
- Manipulation stage bar
- Scam DNA match card
- ShadowPath: likely next step, confidence, evidence
- Risk engine `NORMAL → WATCH → INTERVENE → CRITICAL`, always with "why" chips
- Privacy gate counters
- Reality Pause: full-screen calm interruption with Verify Safely / I'm Not Sure / Continue Anyway

**Scene 2: `/patterns` (pattern engine)**
- Three anonymized incidents with different brands and channels but the same workflow
- Structural similarity computed with longest-common-subsequence over step order
- A new in-progress incident is matched and its next step predicted by voting across known incidents, before the money step

### What is real and what is scripted

| Part | Nature |
|---|---|
| Scene 1 signals, stages, risk levels, Scam DNA %, ShadowPath | **Scripted** timeline in `demo/bankScam.ts` |
| Privacy redaction and counts | **Real code**: regex in `services/sanitize.ts` |
| Scene 2 similarity % and next-step prediction | **Real computation** in `services/patterns.ts` over made-up demo incidents |

### Run it

```bash
npm install
npm run dev
```

Open http://localhost:3000 and click **Start demo**, then open http://localhost:3000/patterns and click **Start**.

Stack: Next.js (App Router), TypeScript, Tailwind CSS, Zustand, React Flow (`@xyflow/react`).

### Structure

```text
app/
  page.tsx               Scene 1 dashboard
  patterns/page.tsx      Scene 2 pattern engine
components/
  AttackGraph/  RealityPause/  RiskEngine/  ManipulationState/
  ScamDNA/  ShadowPath/  PrivacyGate/
hooks/useAegis.ts        Zustand store + timeline player (single source of UI state)
services/
  sanitize.ts            regex PII redaction
  patterns.ts            similarity + next-step prediction
demo/
  bankScam.ts            scripted Scene 1 timeline
  incidents.ts           demo incidents for Scene 2
types/events.ts          event contract
```

---

## Integration guide

### Plugging in a live stream (aegis-realtime → aegis-frontend)

The only swap point is the player in `hooks/useAegis.ts`. Anything that calls `apply(event)` drives the UI:

```ts
import { useAegis } from "@/hooks/useAegis";

export function connect(url: string) {
  const ws = new WebSocket(url);
  ws.onmessage = (m) => useAegis.getState().apply(JSON.parse(m.data));
  return () => ws.close();
}
```

Fix these two things when integrating:
1. `apply()` currently sanitizes `transcript` text and overwrites `privacy` counts from its own redaction. When the real filter in aegis-core sends `privacy` events, remove or merge that logic so real counts are not overwritten.
2. `/patterns` currently reads `demo/incidents.ts` and `services/patterns.ts`. Replace these with an API response from aegis-backend of incidents shaped as `{ id, label, surface, steps[] }`, using the step vocabulary in `demo/incidents.ts` (or agree on a new one in aegis-docs).

Keep the scripted demo available behind a flag. If the live pipeline fails on stage, switch back to it.

### What the other repos should deliver

- **aegis-core**: given sanitized text, return signals, stage, Scam DNA match, and ShadowPath prediction in the event shapes above. Report privacy leakage with a documented measurement method (for example, a labeled test set stored in aegis-data).
- **aegis-realtime**: deliver events in order with a stable `at` timeline. Support replay of a recorded scenario from aegis-data.
- **aegis-backend**: expose the causal graph as `graph_node` events, compute `risk` with `drivers`, decide when to emit `reality_pause`, and serve the incident library for `/patterns`.
- **aegis-data**: anonymized incident library, demo scenarios, and labeled test sets. No real personal data.
- **aegis-docs**: keep the event contract, demo script, and architecture diagram current. This is the source of truth when repos disagree.

---

## Demo script (about 3 minutes)

1. **Scene 1** (`/`): Start demo. Point out, in order: redacted transcript → signals → stage → graph growing → Scam DNA → ShadowPath prediction → risk rising with reasons → **Reality Pause**.
2. **Scene 2** (`/patterns`): Start. Three incidents with different brands but the same workflow → computed similarity → new incident → AEGIS predicts the next step before the money step.
3. Closing line: *"AEGIS doesn't classify scams. It recognizes how they unfold, and interrupts at the right moment."*

## Known limitations

- Scene 1 is a scripted simulation, not live detection.
- Regex redaction misses some PII (for example, unusual name formats).
- The demo incident library has 3 entries and is not real data.
- No authentication, persistence, or multi-language support.
