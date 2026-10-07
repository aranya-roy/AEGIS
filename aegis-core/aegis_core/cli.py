"""aegis-core command line.

    python -m aegis_core.cli demo scenarios/bank_scam.json          # AegisEvents (JSON lines)
    python -m aegis_core.cli extract "Install AnyDesk and tell me the code"
    python -m aegis_core.cli gen-data --out data/gen                # synthetic convs + SFT splits
    python -m aegis_core.cli export-library --out data/library.json # DNA library for aegis-backend
"""

from __future__ import annotations

import argparse
import json
import sys

from .datagen.generator import generate, to_sft_rows, write_jsonl
from .evaluation.splits import leave_one_out
from .extract import build_extractor
from .library import default_library
from .pipeline import AegisSession
from .privacy import redact

# Held out of training entirely: used to test workflow generalization.
TEST_FAMILIES = ("telecom_sim", "lottery_fee", "benign_bill")


def cmd_demo(a) -> None:
    sc = json.load(open(a.scenario, encoding="utf-8"))
    s = AegisSession(extractor=build_extractor(a.extractor))
    for t in sc["turns"]:
        for e in s.feed(t):
            print(json.dumps(e, ensure_ascii=False))
    if a.analysis:
        print(json.dumps(s.analysis(), indent=1, ensure_ascii=False), file=sys.stderr)


def cmd_extract(a) -> None:
    red = redact(a.text).text
    ev = build_extractor(a.extractor).extract(red, a.speaker)
    print(json.dumps({"sanitized": red, "event": ev.model_dump(mode="json") if ev else None}, indent=1, ensure_ascii=False))


def cmd_gen(a) -> None:
    convs = generate(a.n, seed=a.seed)
    write_jsonl(convs, f"{a.out}/conversations.jsonl")
    train = [c for c in convs if c["family"] not in TEST_FAMILIES]
    test = [c for c in convs if c["family"] in TEST_FAMILIES]
    # val = a slice of train families, by conversation (never by turn)
    val = train[::10]
    train = [c for c in train if c not in val]
    for name, part in (("train", train), ("val", val), ("test", test)):
        write_jsonl(to_sft_rows(part), f"{a.out}/sft_{name}.jsonl")
    for axis, value in (("lang", "hi"), ("channel", "telegram")):
        _, held = leave_one_out(convs, axis, value)
        write_jsonl(to_sft_rows(held), f"{a.out}/sft_heldout_{axis}_{value}.jsonl")
    print(f"{len(convs)} conversations -> {a.out}/ (train {len(train)}, val {len(val)}, test families {TEST_FAMILIES})")


def cmd_export(a) -> None:
    lib = default_library()
    out = {"incidents": lib.export(), "patterns": [p.to_dict() for p in lib.patterns.patterns],
           "frontend_incidents": lib.frontend_incidents()}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"{len(out['incidents'])} incidents, {len(out['patterns'])} patterns -> {a.out}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="aegis-core")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo"); d.add_argument("scenario"); d.add_argument("--extractor"); d.add_argument("--analysis", action="store_true")
    d.set_defaults(fn=cmd_demo)
    e = sub.add_parser("extract"); e.add_argument("text"); e.add_argument("--speaker", default="caller"); e.add_argument("--extractor")
    e.set_defaults(fn=cmd_extract)
    g = sub.add_parser("gen-data"); g.add_argument("--out", default="data/gen"); g.add_argument("--n", type=int, default=60); g.add_argument("--seed", type=int, default=13)
    g.set_defaults(fn=cmd_gen)
    x = sub.add_parser("export-library"); x.add_argument("--out", default="data/library.json")
    x.set_defaults(fn=cmd_export)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
