import json
from pathlib import Path

from aegis_core.dna import Fingerprint, similarity
from aegis_core.extract.grounding import ground
from aegis_core.extract.rules import RuleExtractor
from aegis_core.pipeline import AegisSession
from aegis_core.privacy import redact
from aegis_core.schema import SemanticEvent, SignalHit
from aegis_core.taxonomy import Signal, Step

ROOT = Path(__file__).resolve().parents[1]
X = RuleExtractor()


def test_redaction_keeps_type_drops_value():
    r = redact("Call 9876543210, UPI ravi.k@oksbi, OTP is 482913, this is Amit Sharma")
    assert "9876543210" not in r.text and "[PHONE]" in r.text
    assert "[UPI]" in r.text and "OTP is [OTP]" in r.text and "Amit" not in r.text


def test_multilingual_signals():
    assert Signal.REMOTE_ACCESS in X.extract("Install this app and share the code").signals()
    assert Signal.SECRECY in X.extract("kisi ko mat batana, case darj hai").signals()
    assert Signal.CREDENTIAL_REQUEST in X.extract("तुरंत ओटीपी बताइए").signals()


def test_negated_request_is_safety_advice():
    s = X.extract("We will never ask for your OTP. Do not share your OTP with anyone.").signals()
    assert Signal.SAFETY_ADVICE in s and Signal.CREDENTIAL_REQUEST not in s


def test_evidence_is_exact_substring():
    text = "Sir, your account will be frozen in 10 minutes. Call me back on [PHONE] only."
    for h in X.extract(text).manipulation_signals:
        assert h.evidence in text


def test_grounding_drops_hallucinated_signal():
    ev = SemanticEvent(manipulation_signals=[
        SignalHit(signal=Signal.URGENCY, evidence="within 10 minutes"),
        SignalHit(signal=Signal.REMOTE_ACCESS, evidence="install AnyDesk now"),
    ], requested_action="INSTALL_APP", confidence=0.9)
    g, rep = ground(ev, "Please do it within 10 minutes.")
    assert g.signals() == {Signal.URGENCY}
    assert rep.hallucinated == 1 and g.requested_action.value == "NONE"


def test_dna_is_brand_and_language_invariant():
    a = Fingerprint.from_steps([Step.AUTHORITY, Step.URGENCY, Step.REMOTE_ACCESS, Step.TRANSFER])
    b = Fingerprint.from_steps([Step.AUTHORITY, Step.URGENCY, Step.REMOTE_ACCESS, Step.TRANSFER])
    c = Fingerprint.from_steps([Step.LURE, Step.TRUST, Step.TRANSFER])
    assert similarity(a, b) == 1.0 and similarity(a, c) < 0.5


def test_pipeline_emits_only_core_events_and_predicts_ahead():
    sc = json.loads((ROOT / "scenarios" / "bank_scam.json").read_text())
    s = AegisSession()
    events = s.run(sc["turns"])
    types = {e["type"] for e in events}
    assert types <= {"transcript", "privacy", "signal", "stage", "scam_dna", "shadowpath"}
    assert all("9876543210" not in json.dumps(e) for e in events)
    preds = [e["next"] for e in events if e["type"] == "shadowpath"]
    assert "Credential request" in preds  # predicted before the OTP turn
    a = s.analysis()
    assert a["stage"]["current"] == "MONEY_MOVEMENT"
    assert a["scam_dna"]["pattern"] == "Remote-access financial fraud"


def test_ensemble_merges_grounded_llm_and_skips_victim_turns():
    from aegis_core.extract import EnsembleExtractor

    class FakeLLM:
        name = "llm"
        calls = 0

        def extract(self, text, speaker="caller", turn_index=0, context=None):
            FakeLLM.calls += 1
            return SemanticEvent(manipulation_signals=[
                SignalHit(signal=Signal.PAYMENT_REQUEST, evidence="top up 5000 in your task wallet"),
                SignalHit(signal=Signal.SECRECY, evidence="tell nobody"),  # not in text: must be dropped
            ], requested_action="TRANSFER_MONEY", confidence=0.8, source="llm")

    ens = EnsembleExtractor(FakeLLM(), budget_ms=2000)
    ev = ens.extract("To unlock VIP tasks you first top up 5000 in your task wallet.")
    assert ev.signals() == {Signal.PAYMENT_REQUEST}
    assert ev.requested_action.value == "TRANSFER_MONEY"
    ens.extract("Okay, I will do it.", speaker="user")
    assert FakeLLM.calls == 1


def test_english_authority_and_id_request():
    s = X.extract("My name is Officer Johnson from the Social Security Administration.").signals()
    assert Signal.AUTHORITY_CLAIM in s
    s = X.extract("Can you please confirm your social security number for me?").signals()
    assert Signal.PERSONAL_INFO_REQUEST in s


def test_plausibility_rejects_mislabelled_quote():
    ev = SemanticEvent(manipulation_signals=[
        SignalHit(signal=Signal.ISOLATION, evidence="Sure thing."),
        SignalHit(signal=Signal.PAYMENT_REQUEST, evidence="top up 5000 in your task wallet"),
    ], confidence=0.9)
    g, rep = ground(ev, "Sure thing. Now top up 5000 in your task wallet.")
    assert g.signals() == {Signal.PAYMENT_REQUEST} and rep.hallucinated == 1


def test_unpressured_payment_does_not_reach_money_stage():
    s = AegisSession()
    s.feed({"speaker": "caller", "text": "Please pay the amount to this account."})
    assert s.msm.current is None or s.msm.current.value not in ("COMPLIANCE", "MONEY_MOVEMENT")
    s.feed({"speaker": "caller", "text": "Otherwise your account will be blocked within 10 minutes."})
    assert s.msm.current.value == "MONEY_MOVEMENT"
