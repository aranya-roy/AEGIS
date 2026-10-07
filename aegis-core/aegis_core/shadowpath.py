"""ShadowPath - WHAT WILL THE ATTACKER DO NEXT?

Variable-order Markov model over workflow steps learned from the incident
library, with back-off from order 3 to order 1, blended with the next step
of the best-matching Scam DNA prototype.

Why not an LLM or a sequence transformer? With ~10 step types and a few
hundred-thousand incidents at most, count-based models are exact,
auditable (every prediction cites its support counts) and train in
milliseconds. A neural model is only worth it once there is real
incident volume; the interface stays the same.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from .dna import DNAMatch, Fingerprint
from .taxonomy import STEP_LABEL, Step

END = "END"


@dataclass
class Prediction:
    next: Step
    probability: float
    support: int
    order: int
    evidence: list[str]

    @property
    def confidence(self) -> int:
        # Down-weight predictions backed by few incidents.
        return int(round(100 * self.probability * min(1.0, (self.support / 8) ** 0.5)))


class ShadowPath:
    def __init__(self, sequences: list[list[Step]], max_order: int = 3):
        self.max_order = max_order
        self.counts: dict[tuple, Counter] = defaultdict(Counter)
        for seq in sequences:
            toks = [s.value for s in seq] + [END]
            for i in range(len(toks)):
                for k in range(1, max_order + 1):
                    if i - k < 0:
                        break
                    self.counts[tuple(toks[i - k:i])][toks[i]] += 1
        self.n_sequences = len(sequences)

    def distribution(self, steps: list[Step]) -> tuple[Counter, int]:
        toks = [s.value for s in steps]
        for k in range(min(self.max_order, len(toks)), 0, -1):
            c = self.counts.get(tuple(toks[-k:]))
            if c and sum(c.values()) >= 3:
                return c, k
        return Counter(), 0

    def predict(self, live: Fingerprint, match: DNAMatch | None = None) -> Prediction | None:
        if not live.steps:
            return None
        dist, order = self.distribution(live.steps)
        seen = set(live.steps)
        # Candidates: unseen steps (scams rarely announce the same move twice).
        cand = Counter({k: v for k, v in dist.items() if k != END and Step(k) not in seen})
        total = sum(v for k, v in dist.items() if k == END or Step(k) not in seen)
        evidence: list[str] = []

        proto_next = None
        if match and match.pattern and not match.novel:
            proto = match.pattern.prototype.steps
            remaining = [s for s in proto if s not in seen]
            if remaining:
                proto_next = remaining[0]
                bonus = max(1, int(total * 0.5 * match.score))
                cand[proto_next.value] += bonus
                total += bonus
                evidence.append(f"Matched pattern '{match.pattern.name}' continues with {STEP_LABEL[proto_next].lower()}")

        if not cand:
            return None
        best, n = cand.most_common(1)[0]
        prob = n / total if total else 0.0
        if order:
            ctx = " → ".join(STEP_LABEL[s].lower() for s in live.steps[-order:])
            obs = dist.get(best, 0)
            evidence.insert(0, f"After {ctx}: {obs}/{sum(dist.values())} known incidents went to {STEP_LABEL[Step(best)].lower()}")
        return Prediction(Step(best), round(prob, 3), int(total), order, evidence)
