"""Manipulation State Machine - WHERE is the attack?

Stages: TRUST -> AUTHORITY -> URGENCY -> ISOLATION -> COMPLIANCE -> MONEY_MOVEMENT.

Each stage accumulates evidence from observed signals (weight x confidence).
The current stage is the furthest stage whose evidence crosses a threshold.
Real scams skip and reorder stages (lure-first scams never claim authority),
so this is an evidence accumulator over an ordered scale, not a strict
left-to-right automaton. It describes observable communication only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .schema import SemanticEvent, StageEvent
from .taxonomy import SIGNAL_LABEL, SIGNAL_STAGE, SIGNAL_WEIGHT, STAGE_INDEX, STAGE_ORDER, Signal, Stage

THRESHOLD = 0.10
SATURATION = 0.5

# A request to pay / install / share a code is ordinary when nothing in the
# conversation applies pressure. Such asks count at UNPRESSURED_FACTOR until
# a pressure cue appears, then the remainder is added retroactively.
PRESSURE = frozenset({
    Signal.AUTHORITY_CLAIM, Signal.REWARD_LURE, Signal.URGENCY, Signal.THREAT, Signal.CHANNEL_SHIFT,
    Signal.ISOLATION, Signal.SECRECY, Signal.VERIFICATION_DISCOURAGEMENT,
})
ASKS = frozenset({Signal.REMOTE_ACCESS, Signal.CREDENTIAL_REQUEST, Signal.PERSONAL_INFO_REQUEST, Signal.PAYMENT_REQUEST})
# Chosen from the definition of the stage, not tuned (dev sets carry no
# stage labels). AEGIS_PRESSURE_GATE=0 turns it off (recall-first).
UNPRESSURED_FACTOR = 0.15 if os.getenv("AEGIS_PRESSURE_GATE", "1") != "0" else 1.0


@dataclass
class ManipulationStateMachine:
    scores: dict[Stage, float] = field(default_factory=lambda: {s: 0.0 for s in STAGE_ORDER})
    reasons: dict[Stage, str] = field(default_factory=dict)
    current: Stage | None = None
    progress: float = 0.0
    history: list[tuple[int, Stage]] = field(default_factory=list)
    pressured: bool = False
    deferred: dict[Stage, float] = field(default_factory=dict)

    def update(self, ev: SemanticEvent, at: int) -> StageEvent | None:
        if not self.pressured and PRESSURE & ev.signals():
            self.pressured = True
            for st, extra in self.deferred.items():
                self.scores[st] += extra
            self.deferred.clear()
        for h in ev.manipulation_signals:
            st = SIGNAL_STAGE[h.signal]
            if st is None:
                continue
            full = max(SIGNAL_WEIGHT[h.signal], 0.05) * h.confidence
            if h.signal in ASKS and not self.pressured:
                self.scores[st] += full * UNPRESSURED_FACTOR
                self.deferred[st] = self.deferred.get(st, 0.0) + full * (1 - UNPRESSURED_FACTOR)
            else:
                self.scores[st] += full
            if st not in self.reasons:
                self.reasons[st] = f'{SIGNAL_LABEL[h.signal]}: "{h.evidence}"'

        reached = [s for s in STAGE_ORDER if self.scores[s] >= THRESHOLD]
        if not reached:
            return None
        stage = reached[-1]
        idx = STAGE_INDEX[stage]
        progress = round(min(1.0, (idx + min(1.0, self.scores[stage] / SATURATION)) / len(STAGE_ORDER)), 2)
        progress = max(progress, self.progress)  # never visually regress

        changed = stage != self.current and (self.current is None or STAGE_INDEX[stage] > STAGE_INDEX[self.current])
        moved = progress - self.progress >= 0.08
        if not changed and not moved:
            return None
        if changed:
            self.current = stage
            self.history.append((at, stage))
        self.progress = progress
        return StageEvent(at=at, stage=self.current, progress=progress,
                          reason=self.reasons.get(self.current, ""))
