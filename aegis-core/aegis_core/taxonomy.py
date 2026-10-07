"""Shared vocabulary for the AEGIS intelligence layer.

Three levels of abstraction, from fine to coarse:

    Signal  - an observable manipulation cue in one utterance ("asked for OTP")
    Step    - a workflow move used by Scam DNA / ShadowPath ("CREDENTIALS")
    Stage   - a position in the Manipulation State Machine ("COMPLIANCE")

Stage names describe observable communication signals, never the user's
psychological state (see aegis-frontend README, "Shared event contract").
"""

from __future__ import annotations

from enum import Enum


class Stage(str, Enum):
    TRUST = "TRUST"
    AUTHORITY = "AUTHORITY"
    URGENCY = "URGENCY"
    ISOLATION = "ISOLATION"
    COMPLIANCE = "COMPLIANCE"
    MONEY_MOVEMENT = "MONEY_MOVEMENT"


STAGE_ORDER: list[Stage] = list(Stage)
STAGE_INDEX: dict[Stage, int] = {s: i for i, s in enumerate(STAGE_ORDER)}


class Step(str, Enum):
    # The first seven match aegis-frontend demo/incidents.ts exactly.
    AUTHORITY = "AUTHORITY"
    URGENCY = "URGENCY"
    CHANNEL_SHIFT = "CHANNEL_SHIFT"
    ISOLATION = "ISOLATION"
    REMOTE_ACCESS = "REMOTE_ACCESS"
    CREDENTIALS = "CREDENTIALS"
    TRANSFER = "TRANSFER"
    # Extensions needed for lure-first scams (jobs, investment, lottery).
    LURE = "LURE"
    TRUST = "TRUST"


FRONTEND_STEPS: set[Step] = {
    Step.AUTHORITY, Step.URGENCY, Step.CHANNEL_SHIFT, Step.ISOLATION,
    Step.REMOTE_ACCESS, Step.CREDENTIALS, Step.TRANSFER,
}

STEP_LABEL: dict[Step, str] = {
    Step.AUTHORITY: "Authority claim",
    Step.URGENCY: "Urgency",
    Step.CHANNEL_SHIFT: "Channel shift",
    Step.ISOLATION: "Isolation",
    Step.REMOTE_ACCESS: "Remote access",
    Step.CREDENTIALS: "Credential request",
    Step.TRANSFER: "Money transfer",
    Step.LURE: "Reward lure",
    Step.TRUST: "Rapport building",
}

STEP_CODE: dict[Step, str] = {
    Step.AUTHORITY: "AUT", Step.URGENCY: "URG", Step.CHANNEL_SHIFT: "CHN",
    Step.ISOLATION: "ISO", Step.REMOTE_ACCESS: "RMT", Step.CREDENTIALS: "CRD",
    Step.TRANSFER: "TRF", Step.LURE: "LUR", Step.TRUST: "TRS",
}


class Signal(str, Enum):
    AUTHORITY_CLAIM = "AUTHORITY_CLAIM"
    TRUST_BUILDING = "TRUST_BUILDING"
    REWARD_LURE = "REWARD_LURE"
    URGENCY = "URGENCY"
    THREAT = "THREAT"
    CHANNEL_SHIFT = "CHANNEL_SHIFT"
    ISOLATION = "ISOLATION"
    SECRECY = "SECRECY"
    VERIFICATION_DISCOURAGEMENT = "VERIFICATION_DISCOURAGEMENT"
    REMOTE_ACCESS = "REMOTE_ACCESS"
    CREDENTIAL_REQUEST = "CREDENTIAL_REQUEST"
    PERSONAL_INFO_REQUEST = "PERSONAL_INFO_REQUEST"
    PAYMENT_REQUEST = "PAYMENT_REQUEST"
    # Counter-signal: legitimate institutions say this; scammers rarely do.
    SAFETY_ADVICE = "SAFETY_ADVICE"


SIGNAL_STEP: dict[Signal, Step | None] = {
    Signal.AUTHORITY_CLAIM: Step.AUTHORITY,
    Signal.TRUST_BUILDING: Step.TRUST,
    Signal.REWARD_LURE: Step.LURE,
    Signal.URGENCY: Step.URGENCY,
    Signal.THREAT: Step.URGENCY,
    Signal.CHANNEL_SHIFT: Step.CHANNEL_SHIFT,
    Signal.ISOLATION: Step.ISOLATION,
    Signal.SECRECY: Step.ISOLATION,
    Signal.VERIFICATION_DISCOURAGEMENT: Step.ISOLATION,
    Signal.REMOTE_ACCESS: Step.REMOTE_ACCESS,
    Signal.CREDENTIAL_REQUEST: Step.CREDENTIALS,
    Signal.PERSONAL_INFO_REQUEST: Step.CREDENTIALS,
    Signal.PAYMENT_REQUEST: Step.TRANSFER,
    Signal.SAFETY_ADVICE: None,
}

SIGNAL_STAGE: dict[Signal, Stage | None] = {
    Signal.AUTHORITY_CLAIM: Stage.AUTHORITY,
    Signal.TRUST_BUILDING: Stage.TRUST,
    Signal.REWARD_LURE: Stage.TRUST,
    Signal.URGENCY: Stage.URGENCY,
    Signal.THREAT: Stage.URGENCY,
    Signal.CHANNEL_SHIFT: Stage.ISOLATION,
    Signal.ISOLATION: Stage.ISOLATION,
    Signal.SECRECY: Stage.ISOLATION,
    Signal.VERIFICATION_DISCOURAGEMENT: Stage.ISOLATION,
    Signal.REMOTE_ACCESS: Stage.COMPLIANCE,
    Signal.CREDENTIAL_REQUEST: Stage.COMPLIANCE,
    Signal.PERSONAL_INFO_REQUEST: Stage.COMPLIANCE,
    Signal.PAYMENT_REQUEST: Stage.MONEY_MOVEMENT,
    Signal.SAFETY_ADVICE: None,
}

# Evidence weight of a signal. Used by the state machine; exported so the
# backend risk engine can reuse it. Tuned by hand, checked on the eval set.
SIGNAL_WEIGHT: dict[Signal, float] = {
    Signal.AUTHORITY_CLAIM: 0.15,
    Signal.TRUST_BUILDING: 0.05,
    Signal.REWARD_LURE: 0.15,
    Signal.URGENCY: 0.20,
    Signal.THREAT: 0.25,
    Signal.CHANNEL_SHIFT: 0.20,
    Signal.ISOLATION: 0.30,
    Signal.SECRECY: 0.35,
    Signal.VERIFICATION_DISCOURAGEMENT: 0.35,
    Signal.REMOTE_ACCESS: 0.45,
    Signal.CREDENTIAL_REQUEST: 0.45,
    Signal.PERSONAL_INFO_REQUEST: 0.25,
    Signal.PAYMENT_REQUEST: 0.50,
    Signal.SAFETY_ADVICE: -0.30,
}

SIGNAL_SEVERITY: dict[Signal, str] = {
    Signal.AUTHORITY_CLAIM: "warn",
    Signal.TRUST_BUILDING: "info",
    Signal.REWARD_LURE: "warn",
    Signal.URGENCY: "warn",
    Signal.THREAT: "warn",
    Signal.CHANNEL_SHIFT: "warn",
    Signal.ISOLATION: "critical",
    Signal.SECRECY: "critical",
    Signal.VERIFICATION_DISCOURAGEMENT: "critical",
    Signal.REMOTE_ACCESS: "critical",
    Signal.CREDENTIAL_REQUEST: "critical",
    Signal.PERSONAL_INFO_REQUEST: "warn",
    Signal.PAYMENT_REQUEST: "critical",
    Signal.SAFETY_ADVICE: "info",
}

SIGNAL_LABEL: dict[Signal, str] = {
    Signal.AUTHORITY_CLAIM: "Authority impersonation",
    Signal.TRUST_BUILDING: "Rapport building",
    Signal.REWARD_LURE: "Reward / refund lure",
    Signal.URGENCY: "Urgency created",
    Signal.THREAT: "Threat of loss or legal action",
    Signal.CHANNEL_SHIFT: "Channel migration",
    Signal.ISOLATION: "Isolation from others",
    Signal.SECRECY: "Secrecy demanded",
    Signal.VERIFICATION_DISCOURAGEMENT: "Discouraged independent verification",
    Signal.REMOTE_ACCESS: "Remote-access request",
    Signal.CREDENTIAL_REQUEST: "Credential request",
    Signal.PERSONAL_INFO_REQUEST: "Personal identity data request",
    Signal.PAYMENT_REQUEST: "Payment instruction",
    Signal.SAFETY_ADVICE: "Genuine safety advice",
}

class ActorClaim(str, Enum):
    BANK = "BANK"
    LAW_ENFORCEMENT = "LAW_ENFORCEMENT"
    GOVERNMENT = "GOVERNMENT"
    COURIER = "COURIER"
    TELECOM = "TELECOM"
    UTILITY = "UTILITY"
    TECH_SUPPORT = "TECH_SUPPORT"
    PAYMENT_APP = "PAYMENT_APP"
    EMPLOYER = "EMPLOYER"
    INVESTMENT = "INVESTMENT"
    FAMILY_OR_FRIEND = "FAMILY_OR_FRIEND"
    LOTTERY = "LOTTERY"
    UNKNOWN = "UNKNOWN"


class Intent(str, Enum):
    GREETING = "GREETING"
    INFORM = "INFORM"
    REASSURE = "REASSURE"
    OFFER = "OFFER"
    THREATEN = "THREATEN"
    REQUEST_ACTION = "REQUEST_ACTION"
    REQUEST_INFO = "REQUEST_INFO"
    VICTIM_RESPONSE = "VICTIM_RESPONSE"


class RequestedAction(str, Enum):
    NONE = "NONE"
    INSTALL_APP = "INSTALL_APP"
    SHARE_OTP = "SHARE_OTP"
    SHARE_CREDENTIALS = "SHARE_CREDENTIALS"
    SHARE_PERSONAL_INFO = "SHARE_PERSONAL_INFO"
    TRANSFER_MONEY = "TRANSFER_MONEY"
    SCAN_QR = "SCAN_QR"
    CLICK_LINK = "CLICK_LINK"
    CALL_NUMBER = "CALL_NUMBER"
    SWITCH_CHANNEL = "SWITCH_CHANNEL"
    STAY_ON_LINE = "STAY_ON_LINE"
    KEEP_SECRET = "KEEP_SECRET"


class Consequence(str, Enum):
    NONE = "NONE"
    DEVICE_TAKEOVER = "DEVICE_TAKEOVER"
    ACCOUNT_TAKEOVER = "ACCOUNT_TAKEOVER"
    DIRECT_TRANSFER = "DIRECT_TRANSFER"
    IDENTITY_THEFT = "IDENTITY_THEFT"
    LOSS_OF_SUPPORT = "LOSS_OF_SUPPORT"


ACTION_CONSEQUENCE: dict[RequestedAction, Consequence] = {
    RequestedAction.NONE: Consequence.NONE,
    RequestedAction.INSTALL_APP: Consequence.DEVICE_TAKEOVER,
    RequestedAction.SHARE_OTP: Consequence.ACCOUNT_TAKEOVER,
    RequestedAction.SHARE_CREDENTIALS: Consequence.ACCOUNT_TAKEOVER,
    RequestedAction.SHARE_PERSONAL_INFO: Consequence.IDENTITY_THEFT,
    RequestedAction.TRANSFER_MONEY: Consequence.DIRECT_TRANSFER,
    RequestedAction.SCAN_QR: Consequence.DIRECT_TRANSFER,
    RequestedAction.CLICK_LINK: Consequence.ACCOUNT_TAKEOVER,
    RequestedAction.CALL_NUMBER: Consequence.LOSS_OF_SUPPORT,
    RequestedAction.SWITCH_CHANNEL: Consequence.LOSS_OF_SUPPORT,
    RequestedAction.STAY_ON_LINE: Consequence.LOSS_OF_SUPPORT,
    RequestedAction.KEEP_SECRET: Consequence.LOSS_OF_SUPPORT,
}

# The single most likely action implied by each signal (used when an
# extractor finds a signal but no explicit action).
SIGNAL_DEFAULT_ACTION: dict[Signal, RequestedAction] = {
    Signal.CHANNEL_SHIFT: RequestedAction.SWITCH_CHANNEL,
    Signal.ISOLATION: RequestedAction.STAY_ON_LINE,
    Signal.SECRECY: RequestedAction.KEEP_SECRET,
    Signal.REMOTE_ACCESS: RequestedAction.INSTALL_APP,
    Signal.CREDENTIAL_REQUEST: RequestedAction.SHARE_CREDENTIALS,
    Signal.PERSONAL_INFO_REQUEST: RequestedAction.SHARE_PERSONAL_INFO,
    Signal.PAYMENT_REQUEST: RequestedAction.TRANSFER_MONEY,
}

ACTION_PRIORITY: list[RequestedAction] = [
    RequestedAction.TRANSFER_MONEY, RequestedAction.SCAN_QR, RequestedAction.SHARE_OTP,
    RequestedAction.SHARE_CREDENTIALS, RequestedAction.INSTALL_APP, RequestedAction.CLICK_LINK,
    RequestedAction.SHARE_PERSONAL_INFO, RequestedAction.KEEP_SECRET,
    RequestedAction.SWITCH_CHANNEL, RequestedAction.CALL_NUMBER,
    RequestedAction.STAY_ON_LINE, RequestedAction.NONE,
]
