"""Privacy gate: redact PII before anything leaves the device.

Three modes, so we can measure the privacy/utility tradeoff:

    none   - raw text (baseline, never used in production)
    typed  - PII replaced by a typed tag: "[UPI]", "[PHONE]" (default)
    masked - every PII span replaced by the same "[REDACTED]" tag

Typed tags keep the *kind* of thing that was said ("caller asked for a UPI
ID") which is what scam detection needs, while dropping the *value*.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

Mode = Literal["none", "typed", "masked"]

# Names: a lead word ("this is", "Mr.", "mera naam", ...) followed by up to two
# name-like words. Case-insensitive on purpose: ASR output is often lowercase.
_NAME_LEAD = re.compile(
    r"\b(this is|i am|i'm|my name is|mera naam|naam|hello|hi|dear|namaste|namaskar|main|speaking with|"
    r"good (?:morning|afternoon|evening)|मेरा नाम|इंस्पेक्टर|नमस्ते|inspector|officer|constable|mr\.?|mrs\.?|ms\.?|dr\.?|shri|smt\.?)\s+",
    re.I,
)
_NAME_WORD = re.compile(r"([a-z][a-z'-]+)\b", re.I)
_JI_NAME = re.compile(r"\b([A-Za-z][a-z]+) ji\b")
_TITLE_LEADS = {"इंस्पेक्टर", "inspector", "officer", "constable", "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "dr", "dr.", "shri", "smt", "smt."}
_NOT_NAME = set("""
a an the to of in on at for from with and or is are am was be not no yes so just also already here there
it its it's me my your you we us our this that sir madam maam ma'am ji everyone all customer team bank police
inspector officer senior manager executive calling speaking connecting going sending adding hiring checking
telling sorry fine ok okay good glad very sure back again interested done ready happy hello hi automated alert
delivery aapka aapki aap bol baat ek mama beta bhai kya mera naam main hoon hai ki ka ke se raha rahi
sbi hdfc icici axis kotak pnb rbi cbi ncb trai fedex dhl paytm phonepe amazon flipkart microsoft airtel jio
support kyc head department office account card haan achha acha theek accha sahi mr mrs ms dr shri smt good
""".split())

# Order matters: longer / more specific patterns first.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("URL", re.compile(r"\b(?:https?://|www\.)\S+|\b(?:bit\.ly|tinyurl\.com|t\.me|wa\.me|rb\.gy)/\S+|\b[\w-]+\.(?:apk|xyz|top|click|link)\b", re.I)),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")),
    ("UPI", re.compile(r"\b[\w.-]{2,}@(?:ok)?[a-z]{2,}\b", re.I)),
    ("CARD", re.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b")),
    ("AADHAAR", re.compile(r"\b[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}\b")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("IFSC", re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")),
    ("PHONE", re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")),
    ("OTP", re.compile(r"(?i)(?P<pre>\b(?:otp|pin|code|cvv)(?:\s+is)?[\s:]+)\d{3,8}\b")),
    ("ACCOUNT", re.compile(r"(?i)(?P<pre>\bending\s+(?:in\s+)?)\d{4}\b|\b\d{9,18}\b")),
]

PII_TYPES = [name for name, _ in _PATTERNS] + ["NAME"]


@dataclass
class RedactionResult:
    text: str
    count: int
    by_type: dict[str, int] = field(default_factory=dict)
    spans: list[tuple[str, str]] = field(default_factory=list)  # (type, original) - stays local


def redact(text: str, mode: Mode = "typed") -> RedactionResult:
    if mode == "none":
        return RedactionResult(text=text, count=0)

    by_type: dict[str, int] = {}
    spans: list[tuple[str, str]] = []

    def tag(kind: str) -> str:
        return "[REDACTED]" if mode == "masked" else f"[{kind}]"

    def sub(kind: str, pattern: re.Pattern[str], s: str) -> str:
        def repl(m: re.Match[str]) -> str:
            by_type[kind] = by_type.get(kind, 0) + 1
            pre = m.groupdict().get("pre") or ""
            spans.append((kind, m.group(0)[len(pre):]))
            return pre + tag(kind)
        return pattern.sub(repl, s)

    out = text
    for kind, pattern in _PATTERNS:
        out = sub(kind, pattern, out)

    out = _redact_names(out, tag, by_type, spans)
    return RedactionResult(text=out, count=sum(by_type.values()), by_type=by_type, spans=spans)


def _redact_names(text: str, tag, by_type: dict[str, int], spans: list) -> str:
    pieces, pos = [], 0
    for m in _NAME_LEAD.finditer(text):
        if m.start() < pos:
            continue
        titled = m.group(1).lower() in _TITLE_LEADS
        words, cur = [], m.end()
        for _ in range(2):
            w = _NAME_WORD.match(text, cur)
            if not w:
                break
            lw = w.group(1).lower()
            if lw in _NOT_NAME or (lw.endswith("ing") and not (titled and not words)):
                break
            words.append(w)
            cur = w.end()
            nxt = re.match(r" (?=[a-z])", text[cur:], re.I)
            if not nxt:
                break
            cur += 1
        if not words:
            continue
        pieces.append(text[pos:m.end()] + tag("NAME"))
        pos = words[-1].end()
        by_type["NAME"] = by_type.get("NAME", 0) + 1
        spans.append(("NAME", text[m.end():pos]))
    pieces.append(text[pos:])
    out = "".join(pieces)

    def ji(m: re.Match[str]) -> str:
        if m.group(1).lower() in _NOT_NAME:
            return m.group(0)
        by_type["NAME"] = by_type.get("NAME", 0) + 1
        spans.append(("NAME", m.group(1)))
        return f"{tag('NAME')} ji"

    return _JI_NAME.sub(ji, out)


def leaked(original_pii: list[str], redacted_text: str) -> list[str]:
    """PII values (known from synthetic data) still present after redaction."""
    norm = re.sub(r"[\s-]", "", redacted_text.lower())
    return [p for p in original_pii if re.sub(r"[\s-]", "", p.lower()) in norm]
