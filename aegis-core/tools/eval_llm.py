"""Compare rules vs rules+LLM on the hand-written held-out set and small
balanced samples of the public OOD test sets. Slow on CPU; sized to finish
in well under an hour with a 3B model.

    AEGIS_LLM_MODEL=qwen2.5:3b AEGIS_LLM_TIMEOUT_S=120 AEGIS_LLM_BUDGET_MS=120000 \\
        PYTHONPATH=. python tools/eval_llm.py
"""

from __future__ import annotations

import json
import os
import time

from aegis_core.evaluation.external import load_hinglish, load_scam_dialogue, score_all, summarize
from aegis_core.evaluation.run import ROOT, eval_heldout
from aegis_core.extract import build_extractor
from aegis_core.library import default_library


def sample(convs, n):
    pos = [c for c in convs if c["is_scam"]][: n // 2]
    neg = [c for c in convs if not c["is_scam"]][: n // 2]
    return pos + neg


def main() -> None:
    lib = default_library()
    kinds = ["rules", os.getenv("AEGIS_LLM_KIND", "ensemble-local")]
    en = sample(load_scam_dialogue(), int(os.getenv("N_EN", "16")))
    hi = sample(load_hinglish("test"), int(os.getenv("N_HI", "40")))
    report = {"model": os.getenv("AEGIS_LLM_MODEL"), "n_en": len(en), "n_hi": len(hi)}
    for kind in kinds:
        t0 = time.time()
        ho = eval_heldout(kind, lib)
        r = {"heldout": {k: v for k, v in ho.items() if k != "rows"},
             "heldout_rows": [{k: x[k] for k in ("id", "score", "stage", "code")} for x in ho["rows"]],
             "en": summarize(score_all(en, kind)), "hi": summarize(score_all(hi, kind)),
             "seconds": round(time.time() - t0)}
        ext = build_extractor(kind)
        if hasattr(ext, "llm_timeouts"):
            r["llm_timeouts"] = ext.llm_timeouts
        report[kind] = r
        print(kind, json.dumps({k: r[k] for k in ("heldout", "seconds")}), flush=True)
        print("  en", r["en"]["auroc"], "hi", r["hi"]["auroc"], flush=True)
    out = ROOT / "reports" / f"llm_compare_{(os.getenv('AEGIS_LLM_MODEL') or 'llm').replace(':', '_')}.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print("->", out)


if __name__ == "__main__":
    main()
