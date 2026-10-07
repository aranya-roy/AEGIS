"""Incident library: the population memory behind Scam DNA and ShadowPath.

Bootstraps from synthetic scam incidents (no real customer data). In
production aegis-backend appends anonymized fingerprints of confirmed
incidents (steps + tactics only - no text) and rebuilds periodically.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .datagen.generator import FAMILIES, generate
from .dna import Fingerprint, Incident, PatternLibrary
from .shadowpath import ShadowPath
from .taxonomy import Signal, Step

FAMILY_NAMES = {f.name: f.label for f in FAMILIES}


def incidents_from_conversations(convs: list[dict]) -> list[Incident]:
    out = []
    for c in convs:
        if not c.get("is_scam", True):
            continue
        tactics = {Signal(h["signal"]) for t in c["turns"] if t.get("gold")
                   for h in t["gold"]["manipulation_signals"] if h["signal"] != "SAFETY_ADVICE"}
        out.append(Incident(id=c["id"], label=c["label"], surface=c["surface"],
                            fingerprint=Fingerprint.from_steps(c["steps"], tactics), family=c["family"]))
    return out


class Library:
    def __init__(self, incidents: list[Incident]):
        self.incidents = incidents
        self.patterns = PatternLibrary(incidents, names=FAMILY_NAMES)
        self.shadow = ShadowPath([i.fingerprint.steps for i in incidents])

    @classmethod
    def synthetic(cls, n_per_family: int = 25, seed: int = 7, exclude: set[str] | None = None) -> "Library":
        fams = [f.name for f in FAMILIES if f.is_scam and f.name not in (exclude or set())]
        return cls(incidents_from_conversations(generate(n_per_family, seed=seed, families=fams, noise_p=0)))

    @classmethod
    def from_file(cls, path: str | Path) -> "Library":
        data = json.loads(Path(path).read_text())
        incs = [Incident(d["id"], d["label"], d["surface"],
                         Fingerprint.from_steps(d["steps"], {Signal(t) for t in d.get("tactics", [])} or None),
                         d.get("family", "")) for d in data]
        return cls(incs)

    def export(self) -> list[dict]:
        return [{"id": i.id, "label": i.label, "surface": i.surface, "family": i.family,
                 "steps": [s.value for s in i.fingerprint.steps],
                 "tactics": sorted(t.value for t in i.fingerprint.tactics)} for i in self.incidents]

    def frontend_incidents(self, per_pattern: int = 3) -> list[dict]:
        """A few representative incidents per pattern for the /patterns page."""
        by_id = {i.id: i for i in self.incidents}
        out = []
        for p in self.patterns.patterns:
            for mid in p.members[:per_pattern]:
                d = by_id[mid].frontend()
                d["pattern"] = p.name
                out.append(d)
        return out


@lru_cache(maxsize=1)
def default_library() -> Library:
    return Library.synthetic()


__all__ = ["Library", "default_library", "incidents_from_conversations", "Step"]
