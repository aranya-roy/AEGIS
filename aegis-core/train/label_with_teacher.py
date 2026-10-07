"""Distillation: label public / consented transcripts with the Claude teacher,
keep only grounded outputs, and write SFT rows for the local model.

    export ANTHROPIC_API_KEY=...   # or `ant auth login`
    python train/label_with_teacher.py --in data/raw/transcripts.jsonl --out data/gen/sft_teacher.jsonl

Input rows: {"id": "...", "turns": [{"speaker": "caller"|"user", "text": "..."}]}
Text is redacted BEFORE it is sent. Spot-check ~50 labels by hand before
mixing them into training data.
"""

from __future__ import annotations

import argparse
import json

from aegis_core.extract.grounding import ground
from aegis_core.extract.llm_claude import ClaudeExtractor
from aegis_core.extract.prompts import SYSTEM_PROMPT, render_user_message
from aegis_core.privacy import redact


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    teacher = ClaudeExtractor()
    n = kept = 0
    with open(args.inp, encoding="utf-8") as fin, open(args.out, "w", encoding="utf-8") as fout:
        for line in fin:
            conv = json.loads(line)
            hist: list[str] = []
            for i, t in enumerate(conv["turns"]):
                red = redact(t["text"]).text
                ev = teacher.extract(red, t["speaker"], i, hist[-4:])
                n += 1
                if ev is not None:
                    ev, rep = ground(ev, red)
                    if not rep.hallucinated:
                        kept += 1
                        target = ev.model_dump(mode="json", exclude={"turn_index", "speaker", "source"})
                        fout.write(json.dumps({"messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": render_user_message(red, t["speaker"], hist[-4:])},
                            {"role": "assistant", "content": json.dumps(target, ensure_ascii=False)},
                        ], "meta": {"conv": conv["id"], "turn": i, "source": "teacher"}}, ensure_ascii=False) + "\n")
                hist.append(f"[{t['speaker']}] {red}")
    print(f"labeled {kept}/{n} turns (dropped turns with ungrounded teacher output)")


if __name__ == "__main__":
    main()
