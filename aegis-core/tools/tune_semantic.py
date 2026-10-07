"""Tune the semantic tier's (margin, min_sim) on DEV data only:
scam-dialogue train split and the Hinglish dev half. Test splits and the
hand-written held-out set are never read here."""

from __future__ import annotations

import csv
import itertools
import json
import random
import sys

from aegis_core.evaluation.external import EXT, load_hinglish, split_dialogue
from aegis_core.evaluation.run import auroc
from aegis_core.extract import merge
from aegis_core.extract.rules import RuleExtractor
from aegis_core.extract.semantic import NONE, SemanticExtractor, clauses
from aegis_core.library import default_library
from aegis_core.pipeline import AegisSession
from aegis_core.privacy import redact
from aegis_core.schema import SignalHit
from aegis_core.taxonomy import Signal

rng = random.Random(0)
rows = list(csv.DictReader((EXT / "scam_dialogue" / "train.csv").open(encoding="utf-8")))
rng.shuffle(rows)
# first part: benign caller clauses become extra negatives; second part: tuning set
bank_rows, tune_rows = rows[:300], rows[300:]
extra_neg = [c for r in bank_rows if r["label"] == "0" for t in split_dialogue(r["dialogue"])
             if t["speaker"] == "caller" for c in clauses(redact(t["text"]).text)]
tune = [{"is_scam": r["label"] == "1", "turns": split_dialogue(r["dialogue"])} for r in tune_rows[:160]]
tune += [{"is_scam": c["is_scam"], "turns": c["turns"]} for c in load_hinglish("dev")]

sem = SemanticExtractor(extra_negatives=extra_neg)
rules = RuleExtractor()
lib = default_library()

# cache: per turn -> (rules event, [(clause, scores)])
cache = []
for conv in tune:
    turns = []
    for i, t in enumerate(conv["turns"]):
        red = redact(t["text"]).text
        r = rules.extract(red, t["speaker"], i)
        cl = clauses(red) if t["speaker"] == "caller" else []
        turns.append((t, red, r, list(zip(cl, sem.scores(cl)))))
    cache.append((conv["is_scam"], turns))
print("cached", len(cache), "conversations", file=sys.stderr)


class Replay:
    name = "replay"

    def __init__(self, events):
        self.events = iter(events)

    def extract(self, *a, **k):
        return next(self.events)


def run(margin: float, min_sim: float) -> dict:
    pos, neg = [], []
    for is_scam, turns in cache:
        evs = []
        for t, red, r, cs in turns:
            found = {}
            for c, sc in cs:
                for lab, s in sc.items():
                    if lab != NONE and s >= min_sim and s - sc[NONE] >= margin:
                        found.setdefault(Signal(lab), SignalHit(signal=Signal(lab), evidence=c, confidence=0.7))
            sem_ev = r.model_copy(update={"manipulation_signals": list(found.values()), "source": "llm"})
            evs.append(merge(r, sem_ev) if found else r)
        s = AegisSession(extractor=Replay(evs), library=lib)
        s.run([{"speaker": t["speaker"], "text": t["text"]} for t, *_ in turns])
        (pos if is_scam else neg).append(s.evidence_score())
    return {"auroc": round(auroc(pos, neg), 4),
            "benign_any": round(sum(x > 0 for x in neg) / len(neg), 3),
            "scam_any": round(sum(x > 0 for x in pos) / len(pos), 3)}


base = run(9.0, 9.0)  # impossible thresholds = rules only
print("rules only", base)
results = []
for m, ms in itertools.product([0.0, 0.01, 0.02, 0.03, 0.04, 0.06], [0.80, 0.82, 0.84, 0.86]):
    r = run(m, ms)
    results.append(((m, ms), r))
    print(m, ms, r)
best = max(results, key=lambda x: (x[1]["auroc"], -x[1]["benign_any"]))
print("best", json.dumps(best))
