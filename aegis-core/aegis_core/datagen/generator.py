"""Synthetic conversation generator with gold turn-level labels.

Augmentation axes (each is also a held-out split in evaluation/splits.py):
    family   - 10 scam workflows + 5 benign hard-negative workflows
    language - en / hinglish / hi, plus per-turn code-mixing
    brand    - real and fictional brands per actor type
    channel  - call / whatsapp / telegram / sms
    order    - optional moves, adjacent-move swaps, small-talk insertion
    noise    - ASR-style noise (lowercase, no punctuation, char drops)

All PII is fake and generated here, so privacy leakage is measurable.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..extract.lexicon import compile_all
from ..extract.rules import RuleExtractor
from ..privacy import redact
from ..schema import Entity, SemanticEvent, SignalHit
from ..taxonomy import (
    ACTION_CONSEQUENCE, ACTION_PRIORITY, SIGNAL_DEFAULT_ACTION, SIGNAL_STAGE, SIGNAL_STEP,
    STAGE_INDEX, ActorClaim, RequestedAction, Signal, Step,
)
from .templates import CODES, T, VICTIM

_MARK = re.compile(r"\[\[(\w{3}):(.*?)\]\]")
_, _, _, _ENTS = compile_all()

Move = str | tuple[str, float] | list[str]


@dataclass
class Family:
    name: str
    label: str
    actor: ActorClaim
    moves: list[Move]
    brands: list[str]
    is_scam: bool = True
    swappable: list[tuple[str, str]] = field(default_factory=list)
    user_first: str | None = None


BANKS = ["SBI", "HDFC", "ICICI", "Axis", "Kotak", "PNB", "Bharat Union Bank", "Deccan Co-op Bank"]
PAYAPPS = ["Paytm", "PhonePe", "Google Pay", "BHIM", "QuickPay Wallet"]
COURIERS = ["FedEx", "DHL", "Blue Dart", "SwiftShip Logistics"]
POLICE = ["Mumbai", "Delhi", "CBI", "Hyderabad", "Kolkata"]
TELECOMS = ["Airtel", "Jio", "Vi", "BharatNet Mobile"]
UTILITIES = ["MSEB", "BESCOM", "Tata Power", "Adani Electricity", "City Power Board"]
TECH = ["Microsoft", "Windows", "Apple", "NetSecure Antivirus"]
GENERIC = ["TaskEarn", "StarRatings", "Alpha Capital", "Prime Trade Club", "KBC"]
RETAIL = ["Amazon", "Flipkart", "Myntra", "Swiggy"]

FAMILIES: list[Family] = [
    Family("bank_kyc_remote", "Remote-access financial fraud", ActorClaim.BANK,
           ["OPEN_BANK", ("TRUST", .3), "THREAT_ACCOUNT", ("CHANNEL", .5), ("ISOLATION", .5), "REMOTE",
            ["CRED_OTP", "CRED_PIN"], ("NOVERIFY", .3), ("PAY_SAFE", .6)], BANKS,
           swappable=[("CHANNEL", "ISOLATION"), ("THREAT_ACCOUNT", "TRUST")]),
    Family("digital_arrest", "Digital-arrest extortion", ActorClaim.LAW_ENFORCEMENT,
           ["OPEN_COURIER", "THREAT_LEGAL", "OPEN_POLICE", "CHANNEL", "ISOLATION", "SECRECY", ("NOVERIFY", .5),
            ("PERSONAL", .5), "PAY_SAFE"], COURIERS,
           swappable=[("ISOLATION", "SECRECY"), ("SECRECY", "NOVERIFY")]),
    Family("upi_refund", "Refund / QR reversal fraud", ActorClaim.PAYMENT_APP,
           ["OPEN_PAYAPP", "LURE_REFUND", ("TRUST", .5), ("REMOTE", .5), ["PAY_QR", "CRED_PIN"]], PAYAPPS,
           swappable=[("LURE_REFUND", "TRUST")]),
    Family("utility_disconnect", "Utility disconnection scam", ActorClaim.UTILITY,
           ["OPEN_UTILITY", "THREAT_POWER", "CHANNEL", ("REMOTE", .7), "PAY_FEE"], UTILITIES,
           swappable=[("CHANNEL", "THREAT_POWER")]),
    Family("task_job", "Task-based job scam", ActorClaim.EMPLOYER,
           ["LURE_JOB", ("TRUST", .7), "CHANNEL", "PAY_FEE"], GENERIC,
           swappable=[("TRUST", "CHANNEL")]),
    Family("investment_group", "Investment / trading-group scam", ActorClaim.INVESTMENT,
           ["LURE_INVEST", ("TRUST", .7), "CHANNEL", ("SECRECY", .3), "PAY_FEE"], GENERIC,
           swappable=[("TRUST", "CHANNEL")]),
    Family("tech_support", "Tech-support remote takeover", ActorClaim.TECH_SUPPORT,
           ["OPEN_TECH", "THREAT_VIRUS", ("ISOLATION", .4), "REMOTE", ["PAY_FEE", "CRED_PIN"]], TECH),
    Family("family_emergency", "Family-emergency impersonation", ActorClaim.FAMILY_OR_FRIEND,
           ["OPEN_FAMILY", "URGENCY_FAMILY", ("SECRECY", .7), "PAY_FAMILY"], ["family"]),
    Family("telecom_sim", "SIM / TRAI verification scam", ActorClaim.TELECOM,
           ["OPEN_TELECOM", "THREAT_SIM", ("OPEN_POLICE", .4), "CHANNEL", "PERSONAL", "CRED_OTP"], TELECOMS,
           swappable=[("CHANNEL", "PERSONAL")]),
    Family("lottery_fee", "Lottery advance-fee fraud", ActorClaim.LOTTERY,
           ["LURE_PRIZE", ("TRUST", .5), ("SECRECY", .4), "PAY_FEE"], GENERIC),
    # ---- benign hard negatives ----
    Family("benign_bank_alert", "Genuine bank alert", ActorClaim.BANK,
           ["BENIGN_BANK_OPEN", "BENIGN_BANK_SAFETY"], BANKS, is_scam=False),
    Family("benign_delivery", "Genuine delivery call", ActorClaim.COURIER,
           ["BENIGN_DELIVERY", ("SMALLTALK", .5)], RETAIL, is_scam=False),
    Family("benign_support", "User-initiated support call", ActorClaim.PAYMENT_APP,
           ["BENIGN_SUPPORT"], PAYAPPS + RETAIL, is_scam=False,
           user_first="Hi, my refund for last week's order has not come yet."),
    Family("benign_friend", "Personal call", ActorClaim.UNKNOWN,
           ["BENIGN_FRIEND", ("SMALLTALK", .3)], ["friend"], is_scam=False),
    Family("benign_bill", "Genuine bill reminder", ActorClaim.UTILITY,
           ["BENIGN_BILL"], UTILITIES, is_scam=False),
]
FAMILY_BY_NAME = {f.name: f for f in FAMILIES}

MOVE_ACTOR = {
    "OPEN_BANK": ActorClaim.BANK, "OPEN_PAYAPP": ActorClaim.PAYMENT_APP, "OPEN_COURIER": ActorClaim.COURIER,
    "OPEN_POLICE": ActorClaim.LAW_ENFORCEMENT, "OPEN_TELECOM": ActorClaim.TELECOM, "OPEN_UTILITY": ActorClaim.UTILITY,
    "OPEN_TECH": ActorClaim.TECH_SUPPORT, "OPEN_FAMILY": ActorClaim.FAMILY_OR_FRIEND,
    "LURE_JOB": ActorClaim.EMPLOYER, "LURE_INVEST": ActorClaim.INVESTMENT, "LURE_PRIZE": ActorClaim.LOTTERY,
    "BENIGN_BANK_OPEN": ActorClaim.BANK, "BENIGN_DELIVERY": ActorClaim.COURIER, "BENIGN_BILL": ActorClaim.UTILITY,
}
MOVE_ACTION = {"CRED_OTP": RequestedAction.SHARE_OTP, "PAY_QR": RequestedAction.SCAN_QR}

CHANNELS = ["call", "call", "whatsapp", "telegram", "sms"]
LANGS = ["en", "en", "hinglish", "hi"]
FIRST = ["Ravi", "Priya", "Arjun", "Meena", "Suresh", "Anita", "Kiran", "Deepak", "Lakshmi", "Farhan"]
LAST = ["Kumar", "Sharma", "Reddy", "Iyer", "Verma", "Khan", "Das", "Patel", "Nair", "Singh"]


def _fake(rng: random.Random) -> dict[str, str]:
    acct = "".join(rng.choice("0123456789") for _ in range(rng.randint(11, 14)))
    first = rng.choice(FIRST)
    return {
        "victim": f"{first} {rng.choice(LAST)}" if rng.random() < .5 else f"Mr. {first} {rng.choice(LAST)}",
        "agent": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
        "phone": rng.choice("6789") + "".join(rng.choice("0123456789") for _ in range(9)),
        "upi": f"{first.lower()}{rng.randint(10, 99)}@ok{rng.choice(['sbi', 'axis', 'hdfc', 'icici'])}",
        "acct": acct, "acct4": acct[-4:],
        "amount": f"{rng.choice([499, 1999, 4999, 9999, 25000, 49000, 150000]):,}",
    }


def _asr_noise(s: str, rng: random.Random) -> str:
    s = re.sub(r"[.,!?;:]", "", s.lower())
    return "".join(c for c in s if not (c.isalpha() and rng.random() < 0.01))


def render(template: str, slots: dict[str, str], noise: bool, rng: random.Random) -> tuple[str, list[tuple[str, str]]]:
    """Return (text, [(signal_code, evidence)]) with evidence an exact substring."""
    filled = template.format(**{k: v for k, v in slots.items()})
    out, spans, pos = [], [], 0
    for m in _MARK.finditer(filled):
        plain = filled[pos:m.start()]
        out.append(_asr_noise(plain, rng) if noise else plain)
        ev = _asr_noise(m.group(2), rng) if noise else m.group(2)
        out.append(ev)
        spans.append((m.group(1), ev))
        pos = m.end()
    tail = filled[pos:]
    out.append(_asr_noise(tail, rng) if noise else tail)
    return "".join(out), spans


def _pick_template(move: str, lang: str, rng: random.Random) -> tuple[str, str]:
    pool = T[move]
    if lang == "hinglish" and rng.random() < .2:  # code-mixing
        lang = "en"
    if lang not in pool:
        lang = "en"
    return rng.choice(pool[lang]), lang


def _expand(moves: list[Move], fam: Family, rng: random.Random) -> list[str]:
    seq: list[str] = []
    for m in moves:
        if isinstance(m, tuple):
            if rng.random() < m[1]:
                seq.append(m[0])
        elif isinstance(m, list):
            seq.append(rng.choice(m))
        else:
            seq.append(m)
    for a, b in fam.swappable:
        if a in seq and b in seq and rng.random() < .3:
            i, j = seq.index(a), seq.index(b)
            seq[i], seq[j] = seq[j], seq[i]
    if rng.random() < .25 and len(seq) > 1:
        seq.insert(rng.randint(1, len(seq)), "SMALLTALK")
    return seq


def gold_event(text_redacted: str, spans: list[tuple[str, str]], move: str, turn_index: int) -> SemanticEvent:
    hits: dict[Signal, SignalHit] = {}
    for code, ev in spans:
        sig = Signal(CODES[code])
        evr = redact(ev).text.strip()
        hits.setdefault(sig, SignalHit(signal=sig, evidence=evr, confidence=1.0))
    signals = set(hits)
    cands = {SIGNAL_DEFAULT_ACTION[s] for s in signals if s in SIGNAL_DEFAULT_ACTION}
    if move in MOVE_ACTION and cands:
        cands.add(MOVE_ACTION[move])
        cands.discard(RequestedAction.SHARE_CREDENTIALS)
    action = next(a for a in ACTION_PRIORITY if a in cands | {RequestedAction.NONE})
    stages = [SIGNAL_STAGE[s] for s in signals if SIGNAL_STAGE[s]]
    entities, seen = [], set()
    for t, p in _ENTS:
        for m in p.finditer(text_redacted):
            if (t, m.group(0).lower()) not in seen:
                seen.add((t, m.group(0).lower()))
                entities.append(Entity(type=t, value=m.group(0)))
    return SemanticEvent(
        turn_index=turn_index, speaker="caller",
        actor_claim=MOVE_ACTOR.get(move, ActorClaim.UNKNOWN),
        communication_intent=RuleExtractor._intent("caller", signals, action, turn_index),
        manipulation_signals=sorted(hits.values(), key=lambda h: h.signal.value),
        requested_action=action, financial_consequence=ACTION_CONSEQUENCE[action],
        stage=max(stages, key=lambda s: STAGE_INDEX[s], default=None),
        entities=entities, confidence=1.0 if hits else 0.2, source="gold",
    )


def generate_conversation(fam: Family, rng: random.Random, idx: int, lang: str | None = None,
                          brand: str | None = None, channel: str | None = None, noise_p: float = .2) -> dict:
    lang = lang or rng.choice(LANGS)
    brand = brand or rng.choice(fam.brands)
    channel = channel or rng.choice(CHANNELS)
    noise = rng.random() < noise_p
    slots = {**_fake(rng), "brand": brand, "police": rng.choice(POLICE)}
    turns: list[dict] = []
    at = 500
    pii_all: list[str] = []
    if fam.user_first:
        turns.append({"speaker": "user", "text": fam.user_first, "at": at, "move": "USER_OPEN", "pii": [], "gold": None})
        at += 2500
    for move in _expand(fam.moves, fam, rng):
        template, used_lang = _pick_template(move, lang, rng)
        text, spans = render(template, slots, noise, rng)
        pii = [slots[k] for k in ("victim", "agent", "phone", "upi", "acct") if "{" + k + "}" in template]
        if "{acct4}" in template:
            pii.append(slots["acct4"])
        pii_all += pii
        red = redact(text).text
        g = gold_event(red, spans, move, len(turns))
        turns.append({"speaker": "caller", "text": text, "at": at, "move": move, "lang": used_lang,
                      "pii": pii, "gold": g.model_dump(mode="json")})
        at += rng.randint(2500, 6000)
        if rng.random() < .7:
            pool = VICTIM.get(lang, VICTIM["en"])
            turns.append({"speaker": "user", "text": rng.choice(pool), "at": at, "move": "VICTIM", "pii": [], "gold": None})
            at += rng.randint(1500, 3000)

    steps: list[str] = []
    for t in turns:
        if t["gold"]:
            for h in t["gold"]["manipulation_signals"]:
                st = SIGNAL_STEP[Signal(h["signal"])]
                if st and st.value not in steps:
                    steps.append(st.value)
    return {
        "id": f"{fam.name}-{idx:04d}", "family": fam.name, "label": fam.label, "is_scam": fam.is_scam,
        "lang": lang, "brand": brand, "channel": channel, "noisy": noise,
        "surface": f"{brand} · {channel.capitalize() if channel != 'sms' else 'SMS'}",
        "steps": steps, "turns": turns, "pii": pii_all,
    }


def generate(n_per_family: int = 40, seed: int = 13, families: list[str] | None = None,
             noise_p: float = .2) -> list[dict]:
    rng = random.Random(seed)
    fams = [FAMILY_BY_NAME[f] for f in families] if families else FAMILIES
    out = []
    for fam in fams:
        for i in range(n_per_family):
            out.append(generate_conversation(fam, rng, i, noise_p=noise_p))
    return out


def to_sft_rows(convs: list[dict], context_turns: int = 4) -> list[dict]:
    """Chat-format SFT rows (one per turn) on *redacted* text. Victim turns
    are included with empty targets so the model learns not to over-fire."""
    from ..extract.prompts import SYSTEM_PROMPT, render_user_message
    rows = []
    for c in convs:
        history: list[str] = []
        for i, t in enumerate(c["turns"]):
            red = redact(t["text"]).text
            if t["gold"]:
                g = SemanticEvent.model_validate(t["gold"])
            else:
                g = SemanticEvent(turn_index=i, speaker="user", communication_intent="VICTIM_RESPONSE", source="gold")
            target = g.model_dump(mode="json", exclude={"turn_index", "speaker", "source"})
            rows.append({
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": render_user_message(red, t["speaker"], history[-context_turns:])},
                    {"role": "assistant", "content": json.dumps(target, ensure_ascii=False)},
                ],
                "meta": {"conv": c["id"], "family": c["family"], "lang": t.get("lang", c["lang"]),
                         "brand": c["brand"], "channel": c["channel"], "turn": i},
            })
            history.append(f"[{t['speaker']}] {red}")
    return rows


def write_jsonl(rows: list[dict], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def incident_steps(conv: dict) -> list[Step]:
    return [Step(s) for s in conv["steps"]]
