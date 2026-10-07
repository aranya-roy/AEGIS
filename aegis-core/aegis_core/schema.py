"""Data contracts.

`SemanticEvent` is what every extractor (rules, local LLM, Claude) must
produce for one utterance. Downstream components (graph, state machine,
Scam DNA, ShadowPath, risk) consume only this structure, never raw text.

`AegisEvent` covers the variants of aegis-frontend/types/events.ts that
aegis-core produces (graph_node / risk / reality_pause are aegis-backend's).
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from .taxonomy import (
    ActorClaim, Consequence, Intent, RequestedAction, Signal, Stage,
)

Speaker = Literal["caller", "user"]


class SignalHit(BaseModel):
    signal: Signal
    evidence: str = Field(description="Exact quote from the utterance that shows the signal.")
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


class Entity(BaseModel):
    type: Literal[
        "ORG", "BRAND", "APP", "CHANNEL", "AMOUNT", "DEADLINE",
        "PHONE", "UPI", "ACCOUNT", "EMAIL", "URL", "ID_DOC", "PERSON",
    ]
    value: str


class SemanticEvent(BaseModel):
    """Structured meaning of one utterance. Never a bare scam=true."""

    turn_index: int = 0
    speaker: Speaker = "caller"
    actor_claim: ActorClaim = ActorClaim.UNKNOWN
    communication_intent: Intent = Intent.INFORM
    manipulation_signals: list[SignalHit] = Field(default_factory=list)
    requested_action: RequestedAction = RequestedAction.NONE
    financial_consequence: Consequence = Consequence.NONE
    stage: Stage | None = None
    entities: list[Entity] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    source: Literal["rules", "llm", "ensemble", "gold"] = "rules"

    def signals(self) -> set[Signal]:
        return {h.signal for h in self.manipulation_signals}


class LLMSemanticEvent(BaseModel):
    """Schema the LLM is constrained to. Subset of SemanticEvent: the
    pipeline fills turn_index/speaker/source itself so the model cannot
    hallucinate them."""

    actor_claim: ActorClaim
    communication_intent: Intent
    manipulation_signals: list[SignalHit]
    requested_action: RequestedAction
    financial_consequence: Consequence
    stage: Stage | None
    entities: list[Entity]
    confidence: float


class Turn(BaseModel):
    speaker: Speaker
    text: str
    at: int | None = Field(default=None, description="ms from interaction start")


# ---- AegisEvent (wire format to aegis-backend / aegis-realtime / UI) ----

class TranscriptEvent(BaseModel):
    type: Literal["transcript"] = "transcript"
    at: int
    speaker: Speaker
    text: str


class SignalEvent(BaseModel):
    type: Literal["signal"] = "signal"
    at: int
    label: str
    severity: Literal["info", "warn", "critical"]
    evidence: str


class StageEvent(BaseModel):
    type: Literal["stage"] = "stage"
    at: int
    stage: Stage
    progress: float
    reason: str


class ScamDNAEvent(BaseModel):
    type: Literal["scam_dna"] = "scam_dna"
    at: int
    matchPct: int
    pattern: str
    incidents: int


class ShadowPathEvent(BaseModel):
    type: Literal["shadowpath"] = "shadowpath"
    at: int
    next: str
    confidence: int
    evidence: list[str]


class PrivacyEvent(BaseModel):
    type: Literal["privacy"] = "privacy"
    at: int
    detected: int
    removed: int
    transmitted: int


AegisEvent = Annotated[
    Union[
        TranscriptEvent, SignalEvent, StageEvent, ScamDNAEvent, ShadowPathEvent, PrivacyEvent,
    ],
    Field(discriminator="type"),
]


def dump_event(e: BaseModel) -> dict:
    """Serialize without None fields so optional TS props stay absent."""
    return e.model_dump(mode="json", exclude_none=True)
