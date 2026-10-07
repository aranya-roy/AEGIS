"""Log raw LLM signals on DEV data (Hinglish dev half, scam-dialogue train
split) to find over-firing. Never reads test splits or the held-out set."""

from __future__ import annotations

import csv
import json
import os
import sys

from aegis_core.evaluation.external import EXT, load_hinglish, split_dialogue
from aegis_core.extract.llm_local import LocalLLMExtractor
from aegis_core.extract.rules import RuleExtractor
from aegis_core.privacy import redact

llm, rules = LocalLLMExtractor(), RuleExtractor()
hi = load_hinglish("dev")
items = [c for c in hi if not c["is_scam"]][:20] + [c for c in hi if c["is_scam"]][:10]
rows = list(csv.DictReader((EXT / "scam_dialogue" / "train.csv").open(encoding="utf-8")))
seen_types = set()
for r in rows:
    if r["label"] == "0" and r["type"] not in seen_types or (r["label"] == "0" and len(seen_types) >= 4 and len([i for i in items if i["id"].startswith("en")]) < 6):
        seen_types.add(r["type"])
        items.append({"id": f"en{len(items)}", "is_scam": False, "turns": split_dialogue(r["dialogue"])})
    if len([i for i in items if i["id"].startswith("en")]) >= 6:
        break
out = []
for c in items:
    hist = []
    for t in c["turns"]:
        red = redact(t["text"]).text
        if t["speaker"] == "caller":
            ev = llm.extract(red, "caller", len(hist), hist[-4:])
            r = rules.extract(red)
            rec = {"id": c["id"], "is_scam": c["is_scam"], "text": red,
                   "llm": [(h.signal.value, h.evidence, h.confidence) for h in ev.manipulation_signals] if ev else None,
                   "rules": [h.signal.value for h in r.manipulation_signals], "err": llm.last_error}
            out.append(rec)
            print(json.dumps(rec, ensure_ascii=False), flush=True)
        hist.append(f"[{t['speaker']}] {red}")
