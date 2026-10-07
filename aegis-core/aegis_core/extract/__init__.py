"""Semantic event extraction: rules (real-time floor) + optional LLM, merged."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Protocol

from ..schema import SemanticEvent
from ..taxonomy import ACTION_CONSEQUENCE, ACTION_PRIORITY, SIGNAL_STAGE, STAGE_INDEX, ActorClaim
from .grounding import ground
from .rules import RuleExtractor


class Extractor(Protocol):
    name: str

    def extract(self, text: str, speaker: str = "caller", turn_index: int = 0,
                context: list[str] | None = None) -> SemanticEvent | None: ...


def merge(rules: SemanticEvent, llm: SemanticEvent | None) -> SemanticEvent:
    """Union of grounded signals; LLM fills what rules cannot (actor, intent)."""
    if llm is None:
        return rules
    hits = {h.signal: h for h in rules.manipulation_signals}
    for h in llm.manipulation_signals:
        if h.signal not in hits or hits[h.signal].confidence < h.confidence:
            hits[h.signal] = h
    actions = {rules.requested_action, llm.requested_action}
    action = next(a for a in ACTION_PRIORITY if a in actions)
    stages = [SIGNAL_STAGE[s] for s in hits if SIGNAL_STAGE[s] is not None]
    ents = {(e.type, e.value.lower()): e for e in [*rules.entities, *llm.entities]}
    return rules.model_copy(update={
        "actor_claim": llm.actor_claim if llm.actor_claim is not ActorClaim.UNKNOWN else rules.actor_claim,
        "communication_intent": llm.communication_intent,
        "manipulation_signals": sorted(hits.values(), key=lambda h: h.signal.value),
        "requested_action": action,
        "financial_consequence": ACTION_CONSEQUENCE[action],
        "stage": max(stages, key=lambda s: STAGE_INDEX[s], default=None),
        "entities": list(ents.values()),
        "confidence": max(rules.confidence, llm.confidence),
        "source": "ensemble",
    })


class EnsembleExtractor:
    """Rules always; LLM within a latency budget. If the LLM misses the
    budget the rules result is returned and the turn is not blocked."""

    name = "ensemble"

    def __init__(self, llm: Extractor | None, budget_ms: float = 1500):
        self.rules = RuleExtractor()
        self.llm = llm
        self.budget_s = budget_ms / 1000
        self._pool = ThreadPoolExecutor(max_workers=4) if llm else None
        self.llm_timeouts = 0

    def extract(self, text: str, speaker: str = "caller", turn_index: int = 0,
                context: list[str] | None = None) -> SemanticEvent:
        # Victim turns carry no manipulation signals; skip the LLM call for them.
        use_llm = self._pool is not None and self.llm is not None and speaker == "caller"
        fut = self._pool.submit(self.llm.extract, text, speaker, turn_index, context) if use_llm else None
        r = self.rules.extract(text, speaker, turn_index, context)
        llm_event = None
        if fut is not None:
            try:
                llm_event = fut.result(timeout=self.budget_s)
            except FutureTimeout:
                self.llm_timeouts += 1
        if llm_event is not None:
            llm_event, _ = ground(llm_event, text)
        return merge(r, llm_event)


def build_extractor(kind: str | None = None) -> Extractor:
    kind = (kind or os.getenv("AEGIS_EXTRACTOR", "rules")).lower()
    if kind == "rules":
        return RuleExtractor()
    if kind in ("semantic", "hybrid"):
        from .semantic import HybridExtractor, SemanticExtractor
        return SemanticExtractor() if kind == "semantic" else HybridExtractor()
    if kind in ("local", "ensemble-local"):
        from .llm_local import LocalLLMExtractor
        llm = LocalLLMExtractor()
        return llm if kind == "local" else EnsembleExtractor(llm, float(os.getenv("AEGIS_LLM_BUDGET_MS", "1500")))
    if kind in ("claude", "ensemble-claude"):
        from .llm_claude import ClaudeExtractor
        llm = ClaudeExtractor()
        return llm if kind == "claude" else EnsembleExtractor(llm, float(os.getenv("AEGIS_LLM_BUDGET_MS", "4000")))
    raise ValueError(f"unknown extractor {kind!r}")
