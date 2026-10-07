"""Prompt shared by every LLM backend and by the fine-tuning data, so the
model sees exactly the same instructions at train and inference time."""

from __future__ import annotations

import json

from ..taxonomy import ActorClaim, Consequence, Intent, RequestedAction, Signal, Stage

SIGNAL_DEFS = {
    "AUTHORITY_CLAIM": "Speaker claims to be or represent a bank, police, government, courier, telecom, utility, platform or other institution.",
    "TRUST_BUILDING": "Reassurance or rapport meant to lower guard (\"don't worry, I'm here to help\").",
    "REWARD_LURE": "Unexpected refund, prize, cashback, job income or investment return.",
    "URGENCY": "Time pressure or deadline (\"in 10 minutes\", \"immediately\", \"tonight\").",
    "THREAT": "Threat of loss: account block, SIM block, arrest, legal case, disconnection, virus.",
    "CHANNEL_SHIFT": "Asks to move to another channel or number (WhatsApp, Telegram, video call, call back on X).",
    "ISOLATION": "Keeps the victim on the line or alone (\"don't disconnect\", \"sit alone in a room\").",
    "SECRECY": "Asks the victim to keep the matter secret or not tell family.",
    "VERIFICATION_DISCOURAGEMENT": "Discourages checking with the real bank, branch, police or family.",
    "REMOTE_ACCESS": "Asks to install an app/APK, share screen, or read a code from a remote-support app.",
    "CREDENTIAL_REQUEST": "Asks for OTP, PIN, CVV, password, card number or login.",
    "PERSONAL_INFO_REQUEST": "Asks for Aadhaar, PAN, date of birth, KYC documents, account number.",
    "PAYMENT_REQUEST": "Asks to transfer, pay, deposit, scan a QR, approve a collect request or pay a fee.",
    "SAFETY_ADVICE": "Genuine safety advice (\"never share your OTP\", \"call the number on your card\").",
}

SYSTEM_PROMPT = f"""You are the semantic event extractor of AEGIS, a scam-interruption system.
You read ONE utterance from a live call or chat (plus a few previous turns for context)
and describe what the speaker is doing, as JSON. You do not decide whether the whole
conversation is a scam; downstream systems do that from your structured output.

Rules:
1. Only report signals present in the CURRENT utterance. Context is for disambiguation only.
2. Every manipulation signal must include "evidence": an EXACT, contiguous quote copied
   from the current utterance (same spelling, same language, including tags like [PHONE]).
   If you cannot quote it, do not report it.
3. Text in square brackets ([PHONE], [UPI], [OTP], [NAME], ...) is redacted personal data.
   Treat it as a typed placeholder; never guess its value.
4. A negated request ("never share your OTP") is SAFETY_ADVICE, not CREDENTIAL_REQUEST.
5. Turns spoken by "user" (the potential victim) normally contain no manipulation signals.
6. Describe observable communication only. Never claim to know anyone's mental state.
7. If nothing applies, return an empty signal list, requested_action "NONE", and a low confidence.

Signal definitions:
{json.dumps(SIGNAL_DEFS, indent=1, ensure_ascii=False)}

Allowed values:
actor_claim: {[a.value for a in ActorClaim]}
communication_intent: {[i.value for i in Intent]}
requested_action: {[a.value for a in RequestedAction]}
financial_consequence: {[c.value for c in Consequence]}
stage: {[s.value for s in Stage]} or null
entity types: ORG, BRAND, APP, CHANNEL, AMOUNT, DEADLINE, PHONE, UPI, ACCOUNT, EMAIL, URL, ID_DOC, PERSON

Output only the JSON object."""

FEW_SHOT = [
    (
        "[caller] Sir this is Vikram calling from the KYC department of your bank. Your account will be blocked today if KYC is not updated.",
        {
            "actor_claim": "BANK", "communication_intent": "THREATEN",
            "manipulation_signals": [
                {"signal": "AUTHORITY_CLAIM", "evidence": "calling from the KYC department of your bank", "confidence": 0.9},
                {"signal": "THREAT", "evidence": "Your account will be blocked", "confidence": 0.9},
                {"signal": "URGENCY", "evidence": "today", "confidence": 0.6},
            ],
            "requested_action": "NONE", "financial_consequence": "NONE", "stage": "URGENCY",
            "entities": [], "confidence": 0.85,
        },
    ),
    (
        "[caller] Bas ek kaam kijiye, AnyDesk app install kijiye aur jo 9 digit code aayega woh mujhe bataiye.",
        {
            "actor_claim": "UNKNOWN", "communication_intent": "REQUEST_ACTION",
            "manipulation_signals": [
                {"signal": "REMOTE_ACCESS", "evidence": "AnyDesk app install kijiye", "confidence": 0.95},
            ],
            "requested_action": "INSTALL_APP", "financial_consequence": "DEVICE_TAKEOVER", "stage": "COMPLIANCE",
            "entities": [{"type": "APP", "value": "AnyDesk"}], "confidence": 0.9,
        },
    ),
    (
        "[caller] This is a reminder from your bank. We will never ask for your OTP or PIN on a call.",
        {
            "actor_claim": "BANK", "communication_intent": "REASSURE",
            "manipulation_signals": [
                {"signal": "SAFETY_ADVICE", "evidence": "We will never ask for your OTP or PIN", "confidence": 0.9},
            ],
            "requested_action": "NONE", "financial_consequence": "NONE", "stage": None,
            "entities": [], "confidence": 0.8,
        },
    ),
]


def render_user_message(text: str, speaker: str, context: list[str] | None = None) -> str:
    ctx = "\n".join(context[-4:]) if context else "(start of conversation)"
    return f"<context>\n{ctx}\n</context>\n<current speaker=\"{speaker}\">\n{text}\n</current>"


def chat_messages(text: str, speaker: str, context: list[str] | None = None,
                  few_shot: bool = True) -> list[dict]:
    """OpenAI-style message list. Use few_shot=False for a model fine-tuned
    on our SFT data (it was trained without the examples)."""
    msgs: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for utt, out in FEW_SHOT if few_shot else []:
        spk, body = utt[1:].split("] ", 1)
        msgs.append({"role": "user", "content": render_user_message(body, spk)})
        msgs.append({"role": "assistant", "content": json.dumps(out, ensure_ascii=False)})
    msgs.append({"role": "user", "content": render_user_message(text, speaker, context)})
    return msgs
