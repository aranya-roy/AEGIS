"""Out-of-distribution evaluation on public datasets (never used for training).

    python -m aegis_core.evaluation.fetch_external          # downloads CSVs into data/external/
    python -m aegis_core.evaluation.external [--extractor rules|ensemble-local|...] [--limit N]

Datasets (Apache-2.0, Hugging Face):
  * BothBosu/scam-dialogue (test split): 320 English multi-turn calls, 8 types,
    half scam; negatives include real support, delivery, telemarketing and
    wrong-number calls.
  * ysangam/Indian_Cyber_Scam_PhoneCall_Hinglish_Dataset: 10k Hinglish
    utterances, heavily templated, so we dedupe to unique texts and use only
    the binary label (category labels are inconsistent with the text).

Downloaded files are untrusted data: parsed as CSV only, never executed.
The Hinglish set is split deterministically into dev/test halves by a hash
of the text; only the dev half may be looked at when improving the lexicon.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
from pathlib import Path

from ..extract import build_extractor
from ..library import default_library
from ..pipeline import AegisSession
from .run import ROOT, auroc

EXT = ROOT / "data" / "external"
csv.field_size_limit(10**7)
_TURN = re.compile(r"\b(caller|receiver):\s*", re.I)


def split_dialogue(d: str) -> list[dict]:
    parts = _TURN.split(d)
    turns = []
    for i in range(1, len(parts) - 1, 2):
        text = parts[i + 1].strip()
        if text:
            turns.append({"speaker": "caller" if parts[i].lower() == "caller" else "user", "text": text})
    return turns


def hinglish_split(text: str) -> str:
    return "dev" if int(hashlib.sha1(text.encode()).hexdigest(), 16) % 2 == 0 else "test"


def load_scam_dialogue() -> list[dict]:
    rows = csv.DictReader((EXT / "scam_dialogue" / "test.csv").open(encoding="utf-8"))
    return [{"id": f"sd{i}", "type": r["type"], "is_scam": r["label"] == "1", "turns": split_dialogue(r["dialogue"])}
            for i, r in enumerate(rows)]


def load_hinglish(part: str = "test") -> list[dict]:
    seen: dict[str, bool] = {}
    for r in csv.DictReader((EXT / "hinglish_calls" / "data.csv").open(encoding="utf-8")):
        seen.setdefault(r["text"].strip(), r["label"] == "1")
    return [{"id": f"hg{i}", "type": "hinglish", "is_scam": y, "turns": [{"speaker": "caller", "text": t}]}
            for i, (t, y) in enumerate(sorted(seen.items())) if hinglish_split(t) == part]


def score_all(convs: list[dict], kind: str) -> list[dict]:
    lib = default_library()
    ext = build_extractor(kind)
    out = []
    for c in convs:
        s = AegisSession(extractor=ext, library=lib)
        s.run(c["turns"])
        out.append({**{k: c[k] for k in ("id", "type", "is_scam")}, "score": s.evidence_score(),
                    "stage": s.msm.current.value if s.msm.current else None, "code": s.fingerprint.code})
    return out


def summarize(rows: list[dict]) -> dict:
    pos = [r["score"] for r in rows if r["is_scam"]]
    neg = [r["score"] for r in rows if not r["is_scam"]]
    neg_sorted = sorted(neg)
    # Threshold that keeps false positives at <= 5% of benign conversations.
    thr = neg_sorted[int(0.95 * (len(neg_sorted) - 1))] if neg_sorted else 0.0
    by_type: dict[str, list[float]] = {}
    for r in rows:
        by_type.setdefault(r["type"] + ("+" if r["is_scam"] else "-"), []).append(r["score"])
    return {
        "n": len(rows), "scams": len(pos), "benign": len(neg),
        "auroc": round(auroc(pos, neg), 3),
        "recall_at_5pct_fpr": round(sum(p > thr for p in pos) / len(pos), 3) if pos else None,
        "scams_with_any_signal": round(sum(p > 0 for p in pos) / len(pos), 3) if pos else None,
        "benign_with_any_signal": round(sum(n > 0 for n in neg) / len(neg), 3) if neg else None,
        "mean_score_by_type": {k: round(statistics.mean(v), 3) for k, v in sorted(by_type.items())},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extractor", default="rules")
    ap.add_argument("--limit", type=int, default=0, help="cap conversations per dataset (slow LLM tiers)")
    ap.add_argument("--hinglish-part", default="test", choices=["dev", "test"])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    report = {"extractor": args.extractor}
    for name, loader in (("scam_dialogue_en", load_scam_dialogue),
                         ("hinglish_calls", lambda: load_hinglish(args.hinglish_part))):
        convs = loader()
        if args.limit:
            # balanced subsample: first N/2 scams and N/2 benign, deterministic
            convs = [c for c in convs if c["is_scam"]][: args.limit // 2] + [c for c in convs if not c["is_scam"]][: args.limit // 2]
        rows = score_all(convs, args.extractor)
        report[name] = summarize(rows)
        report[name + "_misses"] = [r for r in rows if r["is_scam"] and r["score"] == 0][:15]
        report[name + "_false_hits"] = sorted((r for r in rows if not r["is_scam"]), key=lambda r: -r["score"])[:10]
        print(name, json.dumps(report[name], indent=1))
    out = Path(args.out or ROOT / "reports" / f"external_{args.extractor}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print("->", out)


if __name__ == "__main__":
    main()
