"""AegisSession: aegis-core's per-interaction entry point, fed turn by turn.

    turn -> privacy gate -> semantic extraction -> state machine
         -> Scam DNA -> ShadowPath

Scope (see aegis-frontend README "Who emits what"): aegis-core emits
`transcript`, `privacy`, `signal`, `stage`, `scam_dna`, `shadowpath`.
The causal graph, `risk` and `reality_pause` belong to aegis-backend and
transport to aegis-realtime; both consume `feed()` output plus
`analysis()` (structured SemanticEvents, fingerprint, prediction).

Events inside a turn get small `at` offsets so their order survives any
timestamp-sorted transport.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .dna import DNAMatch, Fingerprint
from .extract import Extractor, build_extractor
from .extract.rules import RuleExtractor
from .library import Library, default_library
from .privacy import Mode, redact
from .schema import (
    PrivacyEvent, ScamDNAEvent, SemanticEvent, ShadowPathEvent, SignalEvent, TranscriptEvent, Turn, dump_event,
)
from .shadowpath import Prediction
from .state_machine import ManipulationStateMachine
from .taxonomy import SIGNAL_LABEL, SIGNAL_SEVERITY, SIGNAL_WEIGHT, STAGE_INDEX, STEP_LABEL, Signal

TURN_GAP_MS = 3000


@dataclass
class AegisSession:
    extractor: Extractor = field(default_factory=build_extractor)
    library: Library = field(default_factory=default_library)
    privacy_mode: Mode = "typed"

    events_log: list[SemanticEvent] = field(default_factory=list)
    msm: ManipulationStateMachine = field(default_factory=ManipulationStateMachine)
    fingerprint: Fingerprint = field(default_factory=Fingerprint)
    dna: DNAMatch | None = None
    prediction: Prediction | None = None
    history: list[str] = field(default_factory=list)
    pii_detected: int = 0
    last_at: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    _signals_emitted: set[Signal] = field(default_factory=set)
    _last_dna: tuple[str, int] | None = None
    _last_pred: tuple[str, int] | None = None
    _fallback: RuleExtractor = field(default_factory=RuleExtractor)

    def feed(self, turn: Turn | dict) -> list[dict]:
        t0 = time.perf_counter()
        if isinstance(turn, dict):
            turn = Turn.model_validate(turn)
        at = turn.at if turn.at is not None else self.last_at + TURN_GAP_MS
        self.last_at = at
        out: list = []

        # 1. privacy gate - nothing below this line sees raw text
        red = redact(turn.text, self.privacy_mode)
        self.pii_detected += red.count
        out.append(TranscriptEvent(at=at, speaker=turn.speaker, text=red.text))
        if red.count:
            out.append(PrivacyEvent(at=at + 10, detected=self.pii_detected, removed=self.pii_detected, transmitted=0))

        # 2. semantic extraction (LLM extractors may return None -> rules floor)
        idx = len(self.events_log)
        ev = self.extractor.extract(red.text, turn.speaker, idx, self.history[-4:])
        if ev is None:
            ev = self._fallback.extract(red.text, turn.speaker, idx, self.history[-4:])
        self.events_log.append(ev)
        self.history.append(f"[{turn.speaker}] {red.text}")

        t = at + 100
        for h in ev.manipulation_signals:
            sev = SIGNAL_SEVERITY[h.signal]
            if h.signal not in self._signals_emitted or sev == "critical":
                self._signals_emitted.add(h.signal)
                out.append(SignalEvent(at=t, label=SIGNAL_LABEL[h.signal], severity=sev, evidence=h.evidence))  # type: ignore[arg-type]
                t += 50

        # 3. state machine
        st = self.msm.update(ev, t)
        if st:
            out.append(st)
            t += 50

        # 4. Scam DNA
        if self.fingerprint.add(ev) or self.dna is None:
            self.dna = self.library.patterns.match(self.fingerprint)
        if len(self.fingerprint.steps) >= 2 and self.dna:
            name = (self.dna.pattern.name if self.dna.pattern and not self.dna.novel
                    else "Emerging variant (no close match)")
            n = len(self.dna.pattern.members) if self.dna.pattern and not self.dna.novel else 0
            key = (name, self.dna.match_pct)
            if self._last_dna is None or key[0] != self._last_dna[0] or abs(key[1] - self._last_dna[1]) >= 5:
                self._last_dna = key
                out.append(ScamDNAEvent(at=t, matchPct=self.dna.match_pct, pattern=name, incidents=n))
                t += 50

        # 5. ShadowPath
        self.prediction = self.library.shadow.predict(self.fingerprint, self.dna)
        p = self.prediction
        if p and p.confidence >= 35:
            key = (p.next.value, p.confidence)
            if self._last_pred is None or key[0] != self._last_pred[0] or abs(key[1] - self._last_pred[1]) >= 10:
                self._last_pred = key
                out.append(ShadowPathEvent(at=t, next=STEP_LABEL[p.next], confidence=p.confidence, evidence=p.evidence))
                t += 50

        self.latencies_ms.append((time.perf_counter() - t0) * 1000)
        return [dump_event(e) for e in out]

    def run(self, turns: list[Turn | dict]) -> list[dict]:
        events: list[dict] = []
        for t in turns:
            events += self.feed(t)
        return events

    def evidence_score(self) -> float:
        """0..1 ML-side evidence that a manipulation workflow is under way:
        noisy-OR of observed signal weights, stage depth and DNA match.
        Not a risk decision (that is aegis-backend's), but useful for
        ranking and for AUROC-style evaluation."""
        seen: dict = {}
        for ev in self.events_log:
            for h in ev.manipulation_signals:
                seen[h.signal] = max(seen.get(h.signal, 0.0), h.confidence)
        p = 1.0
        for sig, c in seen.items():
            p *= 1 - max(SIGNAL_WEIGHT[sig], 0.0) * c
        safety = 0.6 if Signal.SAFETY_ADVICE in seen else 1.0
        stage = STAGE_INDEX[self.msm.current] / 5 if self.msm.current else 0.0
        dna = self.dna.score if self.dna and len(self.fingerprint.steps) >= 2 else 0.0
        return round(safety * (0.5 * (1 - p) + 0.3 * stage + 0.2 * dna), 4)

    def analysis(self) -> dict:
        """Structured state for aegis-backend (graph, risk, intervention)."""
        d = self.dna
        return {
            "stage": {"current": self.msm.current.value if self.msm.current else None,
                      "progress": self.msm.progress,
                      "scores": {k.value: round(v, 3) for k, v in self.msm.scores.items()}},
            "scam_dna": {
                **self.fingerprint.to_dict(),
                "pattern_id": d.pattern.id if d and d.pattern else None,
                "pattern": d.pattern.name if d and d.pattern else None,
                "match_pct": d.match_pct if d else 0,
                "novel": d.novel if d else True,
            },
            "shadowpath": (
                {"next": self.prediction.next.value, "confidence": self.prediction.confidence,
                 "probability": self.prediction.probability, "support": self.prediction.support,
                 "evidence": self.prediction.evidence} if self.prediction else None
            ),
            "evidence_score": self.evidence_score(),
            "semantic_events": [e.model_dump(mode="json") for e in self.events_log],
            "privacy": {"pii_detected": self.pii_detected, "pii_transmitted": 0, "mode": self.privacy_mode},
            "latency_ms": {"last": round(self.latencies_ms[-1], 2) if self.latencies_ms else None,
                           "max": round(max(self.latencies_ms), 2) if self.latencies_ms else None},
        }
