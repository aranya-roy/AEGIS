"""Scam DNA - IS THIS A KNOWN PATTERN OR A NEW VARIANT?

A conversation becomes a behavioural fingerprint built only from *what the
attacker does*, never from words, brand, language or channel:

    steps    ordered workflow moves (first occurrence)  AUT>URG>CHN>RMT>CRD>TRF
    tactics  set of manipulation signals                {AUTHORITY_CLAIM, URGENCY, ...}
    bigrams  step transitions                           {(AUT,URG), (URG,CHN), ...}

Similarity = 0.5 * order (LCS) + 0.3 * tactic Jaccard + 0.2 * transition Jaccard.

Two scams with different brands, languages and channels but the same
workflow get the same DNA; that is the generalization claim, and
evaluation/run.py tests it with leave-one-{brand,language,channel}-out.

Known incidents are clustered (average linkage) into patterns. A live
conversation is matched against pattern prototypes; a high-risk
conversation that matches nothing well is flagged as an emerging variant.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .schema import SemanticEvent
from .taxonomy import SIGNAL_STEP, STEP_CODE, Signal, Step

W_ORDER, W_TACTIC, W_TRANS = 0.5, 0.3, 0.2
NOVELTY_THRESHOLD = 0.55


@dataclass
class Fingerprint:
    steps: list[Step] = field(default_factory=list)
    tactics: set[Signal] = field(default_factory=set)

    @property
    def bigrams(self) -> set[tuple[Step, Step]]:
        return set(zip(self.steps, self.steps[1:]))

    @property
    def code(self) -> str:
        return ">".join(STEP_CODE[s] for s in self.steps)

    def add(self, ev: SemanticEvent) -> bool:
        """Fold one event in. Returns True if the fingerprint changed."""
        changed = False
        for h in ev.manipulation_signals:
            if h.signal is Signal.SAFETY_ADVICE:
                continue
            if h.signal not in self.tactics:
                self.tactics.add(h.signal)
                changed = True
            st = SIGNAL_STEP[h.signal]
            if st is not None and st not in self.steps:
                self.steps.append(st)
                changed = True
        return changed

    @classmethod
    def from_steps(cls, steps: list[Step | str], tactics: set[Signal] | None = None) -> "Fingerprint":
        st = [Step(s) for s in steps]
        if tactics is None:
            tactics = {sig for sig, step in SIGNAL_STEP.items() if step in st and sig is not Signal.SAFETY_ADVICE}
        return cls(steps=st, tactics=set(tactics))

    def to_dict(self) -> dict:
        return {"code": self.code, "steps": [s.value for s in self.steps],
                "tactics": sorted(t.value for t in self.tactics)}


def lcs(a: list, b: list) -> int:
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            dp[i][j] = dp[i - 1][j - 1] + 1 if a[i - 1] == b[j - 1] else max(dp[i - 1][j], dp[i][j - 1])
    return dp[-1][-1]


def _jac(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


def similarity(a: Fingerprint, b: Fingerprint) -> float:
    """Symmetric similarity of two complete fingerprints, 0..1."""
    if not a.steps or not b.steps:
        return 0.0
    order = 2 * lcs(a.steps, b.steps) / (len(a.steps) + len(b.steps))
    return W_ORDER * order + W_TACTIC * _jac(a.tactics, b.tactics) + W_TRANS * _jac(a.bigrams, b.bigrams)


def partial_similarity(live: Fingerprint, proto: Fingerprint) -> float:
    """How well an in-progress conversation matches the *beginning* of a
    pattern. Coverage of the live steps by the prototype, damped while the
    live conversation is still short (2 steps match almost anything)."""
    if not live.steps or not proto.steps:
        return 0.0
    k = len(live.steps)
    prefix = proto.steps[: max(k + 1, 1)]
    order = lcs(live.steps, prefix) / k
    tactic_cov = len(live.tactics & proto.tactics) / len(live.tactics) if live.tactics else 0.0
    trans = _jac(live.bigrams, set(zip(prefix, prefix[1:]))) if k > 1 else order
    raw = W_ORDER * order + W_TACTIC * tactic_cov + W_TRANS * trans
    damp = min(1.0, (k / 4) ** 0.5)
    return raw * damp


@dataclass
class Pattern:
    id: str
    name: str
    prototype: Fingerprint
    members: list[str]
    families: dict[str, int]

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "incidents": len(self.members),
                "prototype": self.prototype.to_dict(), "families": self.families}


@dataclass
class Incident:
    id: str
    label: str
    surface: str
    fingerprint: Fingerprint
    family: str = ""

    def frontend(self) -> dict:
        """Shape expected by aegis-frontend /patterns ({id,label,surface,steps[]})."""
        from .taxonomy import FRONTEND_STEPS
        return {"id": self.id, "label": self.label, "surface": self.surface,
                "steps": [s.value for s in self.fingerprint.steps if s in FRONTEND_STEPS]}


def cluster(incidents: list[Incident], threshold: float = 0.65) -> list[list[int]]:
    """Average-linkage agglomerative clustering on DNA similarity. O(n^3)
    worst case, fine for a few thousand incidents."""
    n = len(incidents)
    sim = [[similarity(incidents[i].fingerprint, incidents[j].fingerprint) for j in range(n)] for i in range(n)]
    clusters: list[list[int]] = [[i] for i in range(n)]
    while len(clusters) > 1:
        best, pair = -1.0, (0, 0)
        for a in range(len(clusters)):
            for b in range(a + 1, len(clusters)):
                s = sum(sim[i][j] for i in clusters[a] for j in clusters[b]) / (len(clusters[a]) * len(clusters[b]))
                if s > best:
                    best, pair = s, (a, b)
        if best < threshold:
            break
        a, b = pair
        clusters[a] += clusters.pop(b)
    return clusters


def _medoid(members: list[Incident]) -> Fingerprint:
    best, fp = -1.0, members[0].fingerprint
    for m in members:
        s = sum(similarity(m.fingerprint, o.fingerprint) for o in members)
        if s > best:
            best, fp = s, m.fingerprint
    return fp


@dataclass
class DNAMatch:
    pattern: Pattern | None
    score: float
    novel: bool

    @property
    def match_pct(self) -> int:
        return int(round(self.score * 100))


class PatternLibrary:
    def __init__(self, incidents: list[Incident], threshold: float = 0.65, names: dict[str, str] | None = None):
        self.incidents = incidents
        self.patterns: list[Pattern] = []
        for k, idxs in enumerate(cluster(incidents, threshold) if incidents else []):
            members = [incidents[i] for i in idxs]
            fams: dict[str, int] = {}
            for m in members:
                fams[m.family] = fams.get(m.family, 0) + 1
            major = [f for f, c in sorted(fams.items(), key=lambda x: -x[1]) if c / len(members) >= 0.3]
            name = " / ".join((names or {}).get(f) or f or f"Pattern {k + 1}" for f in major)
            self.patterns.append(Pattern(f"P{k + 1}", name, _medoid(members), [m.id for m in members], fams))
        self.patterns.sort(key=lambda p: -len(p.members))
        seen: dict[str, int] = {}
        for i, p in enumerate(self.patterns):
            p.id = f"P{i + 1}"
            seen[p.name] = seen.get(p.name, 0) + 1
            if seen[p.name] > 1:
                p.name = f"{p.name} (variant {seen[p.name]})"

    def match(self, live: Fingerprint, partial: bool = True) -> DNAMatch:
        best, score = None, 0.0
        for p in self.patterns:
            s = partial_similarity(live, p.prototype) if partial else similarity(live, p.prototype)
            if s > score:
                best, score = p, s
        return DNAMatch(best, score, novel=score < NOVELTY_THRESHOLD)

    def nearest_incidents(self, live: Fingerprint, k: int = 3) -> list[tuple[Incident, float]]:
        scored = [(i, similarity(live, i.fingerprint)) for i in self.incidents]
        return sorted(scored, key=lambda x: -x[1])[:k]
