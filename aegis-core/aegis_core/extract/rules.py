"""Tier-0 real-time extractor: compiled multilingual lexicon, ~1 ms/turn.

Always runs. Gives the demo a floor that never depends on a GPU or network,
and every hit carries an exact-substring evidence quote by construction.
"""

from __future__ import annotations

import re

from ..schema import Entity, SemanticEvent, SignalHit
from ..taxonomy import (
    ACTION_CONSEQUENCE, ACTION_PRIORITY, SIGNAL_DEFAULT_ACTION, SIGNAL_STAGE,
    STAGE_INDEX, ActorClaim, Intent, RequestedAction, Signal,
)
from .lexicon import NEGATABLE, NEGATION, compile_all

_SIG, _ACTORS, _ACTIONS, _ENTS = compile_all()
_CLAUSE_BREAK = re.compile(r"[.?!;,।]")


def _clause_prefix(text: str, end: int) -> str:
    """Text between the last clause break and `end` (negation scope)."""
    prefix = text[:end][-40:]
    parts = _CLAUSE_BREAK.split(prefix)
    return parts[-1]

# Hits on these patterns are near-unambiguous; the rest are softer cues.
_STRONG = {Signal.REMOTE_ACCESS, Signal.CREDENTIAL_REQUEST, Signal.SECRECY, Signal.SAFETY_ADVICE}


class RuleExtractor:
    name = "rules"

    def extract(self, text: str, speaker: str = "caller", turn_index: int = 0,
                context: list[str] | None = None) -> SemanticEvent:
        hits: dict[Signal, SignalHit] = {}
        if speaker == "caller":
            for sig, patterns in _SIG.items():
                for p in patterns:
                    m = p.search(text)
                    if not m:
                        continue
                    if sig in NEGATABLE and NEGATION.search(_clause_prefix(text, m.start())):
                        continue
                    conf = 0.9 if sig in _STRONG else 0.75
                    end = m.end()
                    ev = text[m.start():end]
                    if ev.count("[") > ev.count("]"):  # don't cut a [TAG] in half
                        close = text.find("]", end)
                        if close != -1:
                            ev = text[m.start():close + 1]
                    if sig not in hits or hits[sig].confidence < conf:
                        hits[sig] = SignalHit(signal=sig, evidence=ev.strip(), confidence=conf)
                    break

        # "Do not share OTP with anyone" is safety advice, not secrecy.
        if Signal.SAFETY_ADVICE in hits:
            hits.pop(Signal.SECRECY, None)

        signals = set(hits)
        actor = ActorClaim.UNKNOWN
        if speaker == "caller":
            for a, p in _ACTORS:
                if p.search(text):
                    actor = a
                    break

        action = self._action(text, signals)
        stage_signals = [s for s in signals if SIGNAL_STAGE[s] is not None]
        stage = max((SIGNAL_STAGE[s] for s in stage_signals), key=lambda st: STAGE_INDEX[st], default=None)

        entities: list[Entity] = []
        seen: set[tuple[str, str]] = set()
        for t, p in _ENTS:
            for m in p.finditer(text):
                key = (t, m.group(0).lower())
                if key not in seen:
                    seen.add(key)
                    entities.append(Entity(type=t, value=m.group(0)))

        return SemanticEvent(
            turn_index=turn_index,
            speaker=speaker,  # type: ignore[arg-type]
            actor_claim=actor,
            communication_intent=self._intent(speaker, signals, action, turn_index),
            manipulation_signals=sorted(hits.values(), key=lambda h: h.signal.value),
            requested_action=action,
            financial_consequence=ACTION_CONSEQUENCE[action],
            stage=stage,
            entities=entities,
            confidence=max((h.confidence for h in hits.values()), default=0.0),
            source="rules",
        )

    @staticmethod
    def _action(text: str, signals: set[Signal]) -> RequestedAction:
        candidates = {SIGNAL_DEFAULT_ACTION[s] for s in signals if s in SIGNAL_DEFAULT_ACTION}
        if candidates:
            for a, p in _ACTIONS:
                if p.search(text):
                    # Refine a generic action ("share credentials" -> "share OTP").
                    if a is RequestedAction.SHARE_OTP and RequestedAction.SHARE_CREDENTIALS in candidates:
                        candidates.discard(RequestedAction.SHARE_CREDENTIALS)
                        candidates.add(a)
                    elif a is RequestedAction.SCAN_QR and RequestedAction.TRANSFER_MONEY in candidates:
                        candidates.add(a)
                    elif a in (RequestedAction.CLICK_LINK, RequestedAction.CALL_NUMBER):
                        candidates.add(a)
        for a in ACTION_PRIORITY:
            if a in candidates:
                return a
        return RequestedAction.NONE

    @staticmethod
    def _intent(speaker: str, signals: set[Signal], action: RequestedAction, turn_index: int) -> Intent:
        if speaker == "user":
            return Intent.VICTIM_RESPONSE
        if action in (RequestedAction.SHARE_OTP, RequestedAction.SHARE_CREDENTIALS, RequestedAction.SHARE_PERSONAL_INFO):
            return Intent.REQUEST_INFO
        if action is not RequestedAction.NONE:
            return Intent.REQUEST_ACTION
        if Signal.THREAT in signals:
            return Intent.THREATEN
        if Signal.REWARD_LURE in signals:
            return Intent.OFFER
        if Signal.TRUST_BUILDING in signals or Signal.SAFETY_ADVICE in signals:
            return Intent.REASSURE
        if turn_index == 0:
            return Intent.GREETING
        return Intent.INFORM
