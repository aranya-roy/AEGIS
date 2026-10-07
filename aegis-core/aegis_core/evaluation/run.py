"""AEGIS-core evaluation harness.

    python -m aegis_core.evaluation.run                      # rules extractor
    AEGIS_EXTRACTOR=local python -m aegis_core.evaluation.run --quick
    python -m aegis_core.evaluation.run --extractor claude --quick

Sections
  1. extraction   turn-level signal P/R/F1, action/stage accuracy, grounding,
                  per-language breakdown (synthetic test set, unseen seed)
  2. heldout      hand-written conversations in wording the generator never
                  uses, incl. 5 scam families it never produces: step
                  recovery, detection AUROC, false alarms, early warning
  3. dna          leave-one-family-out: does Scam DNA flag an unseen family
                  as novel (AUROC), and does ShadowPath still predict it?
  4. latency      p50/p95 per turn, extractor and full core pipeline
  5. privacy      none / typed / masked redaction: PII leak rate vs utility

Synthetic numbers are optimistic (templates share structure); section 2 is
the number to quote.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

from ..datagen.generator import FAMILIES, generate, read_jsonl
from ..dna import Fingerprint
from ..extract import build_extractor
from ..extract.grounding import normalize
from ..library import Library, incidents_from_conversations
from ..pipeline import AegisSession
from ..privacy import leaked, redact
from ..schema import SemanticEvent
from ..taxonomy import STAGE_INDEX, Signal, Stage, Step

ROOT = Path(__file__).resolve().parents[2]
HELDOUT = ROOT / "data" / "heldout" / "handwritten.jsonl"
MONEY_STEPS = {Step.CREDENTIALS, Step.TRANSFER}


def auroc(pos: list[float], neg: list[float]) -> float:
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"p": round(p, 3), "r": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0,
            "support": tp + fn}


# ---------------------------------------------------------------- 1
def eval_extraction(extractor, convs: list[dict], mode: str = "typed") -> dict:
    per = defaultdict(lambda: [0, 0, 0])
    per_lang = defaultdict(lambda: [0, 0, 0])
    action_ok = stage_ok = n_turns = grounded = n_hits = 0
    for c in convs:
        hist: list[str] = []
        for i, t in enumerate(c["turns"]):
            red = redact(t["text"], mode).text
            pred = extractor.extract(red, t["speaker"], i, hist[-4:])
            hist.append(f"[{t['speaker']}] {red}")
            if pred is None:
                pred = SemanticEvent(turn_index=i, speaker=t["speaker"])
            gold = SemanticEvent.model_validate(t["gold"]) if t["gold"] else SemanticEvent(speaker=t["speaker"])
            g, p = gold.signals(), pred.signals()
            lang = t.get("lang", c["lang"])
            for s in Signal:
                tp, fp, fn = s in g and s in p, s in p and s not in g, s in g and s not in p
                per[s.value][0] += tp; per[s.value][1] += fp; per[s.value][2] += fn
                per_lang[lang][0] += tp; per_lang[lang][1] += fp; per_lang[lang][2] += fn
            n_turns += 1
            action_ok += pred.requested_action == gold.requested_action
            stage_ok += pred.stage == gold.stage
            for h in pred.manipulation_signals:
                n_hits += 1
                grounded += normalize(h.evidence) in normalize(red)
    tot = [sum(v[k] for v in per.values()) for k in range(3)]
    macro = [prf(*v)["f1"] for k, v in per.items() if v[0] + v[2] > 0]
    return {
        "turns": n_turns,
        "micro": prf(*tot),
        "macro_f1": round(statistics.mean(macro), 3) if macro else 0.0,
        "per_signal": {k: prf(*v) for k, v in sorted(per.items()) if v[0] + v[2] > 0},
        "per_language": {k: prf(*v) for k, v in per_lang.items()},
        "action_acc": round(action_ok / n_turns, 3),
        "stage_acc": round(stage_ok / n_turns, 3),
        "grounding_rate": round(grounded / n_hits, 3) if n_hits else 1.0,
    }


# ---------------------------------------------------------------- 2
def conversation_score(sess: AegisSession) -> float:
    return sess.evidence_score()


def eval_heldout(extractor_kind: str, library: Library, mode: str = "typed", path: Path = HELDOUT) -> dict:
    convs = read_jsonl(path)
    rows = []
    for c in convs:
        sess = AegisSession(extractor=build_extractor(extractor_kind), library=library, privacy_mode=mode)
        warned_at = None  # first turn: stage >= COMPLIANCE, or ShadowPath expects credentials/money
        for i, t in enumerate(c["turns"]):
            sess.feed(t)
            p = sess.prediction
            hot = (sess.msm.current is not None and STAGE_INDEX[sess.msm.current] >= STAGE_INDEX[Stage.COMPLIANCE]) or (
                p is not None and p.next in MONEY_STEPS and p.confidence >= 50)
            if hot and warned_at is None:
                warned_at = i
        pred_steps, gold_steps = set(s.value for s in sess.fingerprint.steps), set(c["gold_steps"])
        rows.append({
            "id": c["id"], "family": c["family"], "is_scam": c["is_scam"], "novel": c["novel_family"],
            "score": round(conversation_score(sess), 3),
            "stage": sess.msm.current.value if sess.msm.current else None,
            "dna": sess.dna.pattern.name if sess.dna and sess.dna.pattern else None,
            "dna_pct": sess.dna.match_pct if sess.dna else 0,
            "code": sess.fingerprint.code,
            "step_tp": len(pred_steps & gold_steps), "step_fp": len(pred_steps - gold_steps),
            "step_fn": len(gold_steps - pred_steps),
            "warned_at": warned_at, "money_turn": c.get("money_turn"),
        })
    scams = [r for r in rows if r["is_scam"]]
    benign = [r for r in rows if not r["is_scam"]]
    early = [r for r in scams if r["warned_at"] is not None and r["money_turn"] is not None and r["warned_at"] <= r["money_turn"]]
    fa = [r for r in benign if r["stage"] in ("COMPLIANCE", "MONEY_MOVEMENT")]
    tp, fp, fn = (sum(r[k] for r in scams) for k in ("step_tp", "step_fp", "step_fn"))
    return {
        "conversations": len(rows), "scams": len(scams), "benign": len(benign),
        "detection_auroc": round(auroc([r["score"] for r in scams], [r["score"] for r in benign]), 3),
        "step_recovery": prf(tp, fp, fn),
        "warned_by_money_turn": f"{len(early)}/{len(scams)}",
        "benign_reaching_compliance_stage": f"{len(fa)}/{len(benign)}",
        "novel_family_detected": f"{sum(1 for r in scams if r['novel'] and r['stage'] in ('COMPLIANCE','MONEY_MOVEMENT'))}/{sum(r['novel'] for r in scams)}",
        "rows": rows,
    }


# ---------------------------------------------------------------- 3
def eval_dna_generalization(n: int = 20, seed: int = 101) -> dict:
    scam_fams = [f.name for f in FAMILIES if f.is_scam]
    test = generate(n, seed=seed, families=scam_fams, noise_p=0)
    per_family, novel_scores, known_scores = {}, [], []
    top1 = top3 = total = 0
    top1_known = total_known = 0
    full = Library.synthetic()
    for fam in scam_fams:
        lib = Library.synthetic(exclude={fam})
        held = [c for c in test if c["family"] == fam]
        known = [c for c in test if c["family"] != fam][:len(held)]
        for c in held:
            fp = Fingerprint.from_steps(c["steps"])
            novel_scores.append(lib.patterns.match(fp, partial=False).score)
            t1, t3, tt = _shadow_acc(lib, c["steps"])
            top1 += t1; top3 += t3; total += tt
        for c in known:
            fp = Fingerprint.from_steps(c["steps"])
            known_scores.append(lib.patterns.match(fp, partial=False).score)
        per_family[fam] = round(statistics.mean(lib.patterns.match(Fingerprint.from_steps(c["steps"]), partial=False).score for c in held), 3)
    for c in test:
        t1, _, tt = _shadow_acc(full, c["steps"])
        top1_known += t1; total_known += tt
    # A high-similarity score means "known"; novelty AUROC uses (1 - score).
    return {
        "novelty_auroc_leave_family_out": round(auroc([1 - s for s in novel_scores], [1 - s for s in known_scores]), 3),
        "mean_match_unseen_family": round(statistics.mean(novel_scores), 3),
        "mean_match_seen_family": round(statistics.mean(known_scores), 3),
        "unseen_family_mean_match": per_family,
        "shadowpath_top1_unseen_family": round(top1 / total, 3) if total else None,
        "shadowpath_top3_unseen_family": round(top3 / total, 3) if total else None,
        "shadowpath_top1_seen_family": round(top1_known / total_known, 3) if total_known else None,
    }


def _shadow_acc(lib: Library, steps: list[str]) -> tuple[int, int, int]:
    seq = [Step(s) for s in steps]
    t1 = t3 = n = 0
    for k in range(1, len(seq)):
        live = Fingerprint.from_steps(seq[:k])
        dist, _ = lib.shadow.distribution(live.steps)
        ranked = [s for s, _ in dist.most_common() if s != "END" and Step(s) not in set(live.steps)]
        pred = lib.shadow.predict(live, lib.patterns.match(live))
        first = pred.next.value if pred else (ranked[0] if ranked else None)
        n += 1
        t1 += first == seq[k].value
        t3 += seq[k].value in ([first] + ranked)[:3]
    return t1, t3, n


# ---------------------------------------------------------------- 4
def eval_latency(extractor_kind: str, convs: list[dict], library: Library) -> dict:
    ext = build_extractor(extractor_kind)
    ex_ms, pipe_ms = [], []
    for c in convs:
        for t in c["turns"]:
            red = redact(t["text"]).text
            t0 = time.perf_counter()
            ext.extract(red, t["speaker"])
            ex_ms.append((time.perf_counter() - t0) * 1000)
        sess = AegisSession(extractor=ext, library=library)
        sess.run([{"speaker": t["speaker"], "text": t["text"]} for t in c["turns"]])
        pipe_ms += sess.latencies_ms

    def q(xs, p):
        xs = sorted(xs)
        return round(xs[min(len(xs) - 1, int(p * len(xs)))], 2)

    return {"turns": len(ex_ms), "extractor_p50_ms": q(ex_ms, .5), "extractor_p95_ms": q(ex_ms, .95),
            "pipeline_p50_ms": q(pipe_ms, .5), "pipeline_p95_ms": q(pipe_ms, .95)}


# ---------------------------------------------------------------- 5
def eval_privacy_utility(extractor_kind: str, convs: list[dict], library: Library) -> dict:
    out = {}
    ext = build_extractor(extractor_kind)
    total_pii = sum(len(c["pii"]) for c in convs)
    for mode in ("none", "typed", "masked"):
        leaks = sum(len(leaked(t["pii"], redact(t["text"], mode).text)) for c in convs for t in c["turns"])
        ex = eval_extraction(ext, convs, mode)
        ho = eval_heldout(extractor_kind, library, mode)
        out[mode] = {"pii_leak_rate": round(leaks / total_pii, 4) if total_pii else 0.0,
                     "signal_micro_f1": ex["micro"]["f1"], "heldout_detection_auroc": ho["detection_auroc"],
                     "heldout_step_f1": ho["step_recovery"]["f1"]}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extractor", default=None, help="rules | local | ensemble-local | claude | ensemble-claude")
    ap.add_argument("--quick", action="store_true", help="small synthetic set (for slow LLM extractors)")
    ap.add_argument("--out", default=str(ROOT / "reports" / "eval_report.json"))
    args = ap.parse_args()
    import os
    kind = args.extractor or os.getenv("AEGIS_EXTRACTOR", "rules")
    n = 3 if args.quick else 20
    test = generate(n, seed=101)
    lib = Library.synthetic()
    ext = build_extractor(kind)

    report = {"extractor": kind, "synthetic_test_conversations": len(test)}
    print(f"[1/5] extraction ({kind})"); report["extraction"] = eval_extraction(ext, test)
    print("[2/5] hand-written held-out"); report["heldout"] = eval_heldout(kind, lib)
    print("[3/5] Scam DNA / ShadowPath leave-family-out"); report["dna"] = eval_dna_generalization()
    print("[4/5] latency"); report["latency"] = eval_latency(kind, test[: 60], lib)
    if not args.quick:
        print("[5/5] privacy vs utility"); report["privacy_utility"] = eval_privacy_utility(kind, test, lib)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    brief = {k: v for k, v in report.items() if k not in ("heldout",)}
    brief["heldout"] = {k: v for k, v in report["heldout"].items() if k != "rows"}
    brief["extraction"] = {k: v for k, v in report["extraction"].items() if k not in ("per_signal",)}
    print(json.dumps(brief, indent=1, ensure_ascii=False))
    print(f"full report -> {out}")


if __name__ == "__main__":
    main()
