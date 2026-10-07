"""Anti-hallucination layer.

LLM output is never trusted directly. Every claim must be re-derivable from
the utterance:

* a signal survives only if its evidence quote is found in the utterance
  (exact after normalization, or >= 80% token overlap with a window -> lower
  confidence);
* entities survive only if their value occurs in the utterance;
* requested_action must be supported by a surviving signal;
* financial_consequence and stage are recomputed deterministically from the
  surviving action/signals, so the LLM cannot invent them.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from ..schema import SemanticEvent, SignalHit
from ..taxonomy import (
    ACTION_CONSEQUENCE, SIGNAL_DEFAULT_ACTION, SIGNAL_STAGE, STAGE_INDEX,
    RequestedAction, Signal,
)

_WS = re.compile(r"\s+")
_EDGE = re.compile(r"^[\W_]+|[\W_]+$")

# Actions that need a specific supporting signal.
_ACTION_SUPPORT: dict[RequestedAction, set[Signal]] = {
    RequestedAction.SHARE_OTP: {Signal.CREDENTIAL_REQUEST},
    RequestedAction.SCAN_QR: {Signal.PAYMENT_REQUEST},
    RequestedAction.CLICK_LINK: {Signal.REMOTE_ACCESS, Signal.CREDENTIAL_REQUEST, Signal.PERSONAL_INFO_REQUEST, Signal.PAYMENT_REQUEST, Signal.REWARD_LURE},
    RequestedAction.CALL_NUMBER: {Signal.CHANNEL_SHIFT},
}


# Broad, multilingual cue vocabulary per signal. An evidence quote must
# contain at least one cue for its signal type: this rejects LLM output that
# quotes real text but attaches the wrong meaning to it ("Sure thing." as
# ISOLATION). Much broader than the rule lexicon on purpose; it only has to
# say "this quote could plausibly express that signal".
_CUES: dict[Signal, str] = {
    Signal.AUTHORITY_CLAIM: r"from|officer|inspector|police|bank|department|government|official|calling|bol raha|bol rahi|\bse\b|manager|executive|support|team|agency|administration|customs|cbi|cyber|court|ministry|desk|helpline|headquarters|it's me|i am your|office|board|company|service|cent(?:er|re)|बोल|से|विभाग",
    Signal.TRUST_BUILDING: r"worry|help|safe|secur|trust|assur|protect|concern|chinta|madad|ghabra|bharosa|genuine|legitimate|routine|चिंता|मदद",
    Signal.REWARD_LURE: r"refund|cashback|prize|lotter|\bwon\b|\bwin|earn|profit|return|bonus|reward|gift|doubl|income|commission|inaam|inam|jeet|kama|lucky|इनाम|रिफंड|लॉटरी|मुनाफा|कमा",
    Signal.URGENCY: r"w?ithin|wthin|\bnow\b|\bhours?\b|\bhrs\b|\bminutes?\b|\bmins?\b|today|itself|\baaj\b|\braat\b|ghant|kal tak|immediate|urgent|right away|asap|hurry|quick|deadline|expire|last (?:date|chance|warning|day)|before|tonight|turant|abhi|jaldi|fauran|warna|otherwise|or else|तुरंत|अभी|जल्दी|वरना|आज|रात|घंटे|मिनट",
    Signal.THREAT: r"block|freez|froz|suspend|arrest|\bcase\b|\bfir\b|police|legal|court|jail|penalt|\bfine\b|virus|hack|\bcut\b|disconnect|clos|deactivat|seiz|warrant|fraud|illegal|\bband\b|giraftar|\bkat|compromis|launder|drug|accident|emergency|hospital|crime|suspicious|danger|cancel|terminat|बंद|गिरफ्तार|केस|ब्लॉक|वायरस|कट|फ्रीज",
    Signal.CHANNEL_SHIFT: r"whatsapp|telegram|skype|signal|video|number|call (?:me|back|on|this)|link|\bapp\b|\bsms\b|message|join|group|t\.me|wa\.me|\[phone\]|\[url\]|व्हाट्सएप|टेलीग्राम",
    Signal.ISOLATION: r"disconnect|hang|\bcut\b|\bline\b|stay|alone|room|door|anyone|anybody|family|leave|camera|kaat|akel|rakh|kisi|\bmat\b|अकेले|काट|किसी|मत",
    Signal.SECRECY: r"secret|confidential|\btell\b|anyone|nobody|family|disclose|private|bata|gupt|kisi|गोपनीय|बता|किसी",
    Signal.VERIFICATION_DISCOURAGEMENT: r"bank|branch|police|verify|check|\bcall\b|trust|helpline|number|official|jaane|zaroorat|बैंक",
    Signal.REMOTE_ACCESS: r"\bapp|install|download|apk|screen|remote|desk|viewer|software|tool|access|control|link|\[url\]|ऐप|स्क्रीन",
    Signal.CREDENTIAL_REQUEST: r"otp|\bpin\b|password|cvv|code|card|login|credential|passcode|digit|ओटीपी|पिन|पासवर्ड",
    Signal.PERSONAL_INFO_REQUEST: r"aadhaa?r|\bpan\b|birth|\bdob\b|kyc|document|photo|selfie|address|account number|social security|\bssn\b|\bid\b|identity|आधार|पैन",
    Signal.PAYMENT_REQUEST: r"\bpay|transfer|\bsend|deposit|\bfee|charge|amount|money|\brs\b|₹|rupe|\bupi\b|\bqr\b|account|wallet|top up|paise|paisa|bhej|jama|\$|dollar|price|cost|neft|imps|scan|\[upi\]|\[account\]|पैसे|भेज|भुगतान|फीस|स्कैन|क्यूआर|ट्रांसफर",
    Signal.SAFETY_ADVICE: r"never|don't share|do not share|not share|report|official|helpline|branch|back of|1930|kabhi|na batay|mat batay|कभी|न बताएं",
}
_CUE_RE = {sig: re.compile(p, re.I) for sig, p in _CUES.items()}


def plausible(signal: Signal, evidence: str) -> bool:
    return bool(_CUE_RE[signal].search(evidence))


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    return _EDGE.sub("", _WS.sub(" ", s)).strip()


def _tokens(s: str) -> list[str]:
    return re.findall(r"\w+|\[\w+\]", normalize(s))


def evidence_score(evidence: str, text: str) -> float:
    """1.0 exact substring, else best token-overlap ratio with any window."""
    ev, tx = normalize(evidence), normalize(text)
    if not ev:
        return 0.0
    if ev in tx:
        return 1.0
    et, tt = _tokens(evidence), _tokens(text)
    if not et or not tt:
        return 0.0
    n = len(et)
    best = 0.0
    eset = set(et)
    for i in range(max(1, len(tt) - n + 1)):
        window = set(tt[i:i + n + 2])
        best = max(best, len(eset & window) / len(eset))
    return best


@dataclass
class GroundingReport:
    kept: int = 0
    dropped_signals: list[str] = field(default_factory=list)
    dropped_entities: int = 0
    action_downgraded: bool = False

    @property
    def hallucinated(self) -> int:
        return len(self.dropped_signals)


def ground(event: SemanticEvent, text: str, min_overlap: float = 0.8) -> tuple[SemanticEvent, GroundingReport]:
    rep = GroundingReport()
    kept: dict[Signal, SignalHit] = {}
    for h in event.manipulation_signals:
        score = evidence_score(h.evidence, text)
        if not plausible(h.signal, h.evidence):
            rep.dropped_signals.append(f"{h.signal.value} (implausible): {h.evidence!r}")
            continue
        if score >= 1.0:
            hit = h
        elif score >= min_overlap:
            hit = h.model_copy(update={"confidence": round(h.confidence * score * 0.9, 3)})
        else:
            rep.dropped_signals.append(f"{h.signal.value}: {h.evidence!r}")
            continue
        if h.signal not in kept or kept[h.signal].confidence < hit.confidence:
            kept[h.signal] = hit
    rep.kept = len(kept)
    signals = set(kept)

    ntext = normalize(text)
    entities = [e for e in event.entities if normalize(e.value) and normalize(e.value) in ntext]
    rep.dropped_entities = len(event.entities) - len(entities)

    action = event.requested_action
    if action is not RequestedAction.NONE:
        supported = action in {SIGNAL_DEFAULT_ACTION.get(s) for s in signals}
        supported |= bool(_ACTION_SUPPORT.get(action, set()) & signals)
        if not supported:
            implied = [SIGNAL_DEFAULT_ACTION[s] for s in signals if s in SIGNAL_DEFAULT_ACTION]
            action = implied[0] if implied else RequestedAction.NONE
            rep.action_downgraded = True

    stage_candidates = [SIGNAL_STAGE[s] for s in signals if SIGNAL_STAGE[s] is not None]
    stage = max(stage_candidates, key=lambda st: STAGE_INDEX[st], default=None)
    conf = max((h.confidence for h in kept.values()), default=min(event.confidence, 0.3))

    grounded = event.model_copy(update={
        "manipulation_signals": sorted(kept.values(), key=lambda h: h.signal.value),
        "entities": entities,
        "requested_action": action,
        "financial_consequence": ACTION_CONSEQUENCE[action],
        "stage": stage,
        "confidence": round(min(conf, event.confidence if event.confidence > 0 else conf), 3),
    })
    return grounded, rep
