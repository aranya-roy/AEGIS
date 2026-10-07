"""Semantic (embedding) extractor: catches paraphrases the lexicon misses.

Each caller utterance is split into clauses. Every clause is embedded with a
small multilingual sentence encoder and compared with an exemplar bank:

    positives  gold evidence spans from the span-annotated templates, per signal
    negatives  non-signal text: template filler, victim replies, benign calls

A clause gets signal S when the mean similarity of its k nearest S
exemplars beats the k nearest negatives by `margin`. Evidence is the clause
itself, so it is always an exact substring (grounding holds by
construction). Runs on CPU, roughly 10-40 ms per turn after warm-up.

Model: intfloat/multilingual-e5-small (118M params, ~1.3 GB RSS). Set
AEGIS_EMBED_MODEL to a local folder or a Hugging Face id.
"""

from __future__ import annotations

import os
import random
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

from ..datagen.generator import _fake, render
from ..datagen.templates import CODES, T, VICTIM
from ..schema import SemanticEvent, SignalHit
from ..taxonomy import (
    ACTION_CONSEQUENCE, ACTION_PRIORITY, SIGNAL_DEFAULT_ACTION, SIGNAL_STAGE, STAGE_INDEX, Intent,
    RequestedAction, Signal,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = ROOT.parent / "models" / "multilingual-e5-small"
NONE = "NONE"
_CLAUSE = re.compile(r"[^.?!।;\n]+(?:[.?!।;]+|$)")
_SUBCLAUSE = re.compile(r",\s+|\s+(?:and then|then|aur phir|phir|aur|and)\s+", re.I)


def clauses(text: str, min_words: int = 3) -> list[str]:
    """Exact substrings of `text`: sentences, further split on ', ' / 'and' / 'aur'."""
    out: list[str] = []
    for m in _CLAUSE.finditer(text):
        sent = m.group(0).strip()
        if not sent:
            continue
        parts = [p.strip(" ,.?!;") for p in _SUBCLAUSE.split(sent)]
        parts = [p for p in parts if len(p.split()) >= min_words and p in text]
        whole = sent.strip(" .?!;")
        if len(whole.split()) >= min_words:
            out.append(whole)
        out += [p for p in parts if p != whole]
    return out


def build_bank(seed: int = 3, renders: int = 2, extra_negatives: list[str] | None = None) -> tuple[list[str], list[str]]:
    rng = random.Random(seed)
    texts, labels = [], []
    seen = set()

    def add(t: str, lab: str) -> None:
        t = t.strip(" ,.?!;")
        if len(t.split()) >= 2 and (t, lab) not in seen:
            seen.add((t, lab))
            texts.append(t)
            labels.append(lab)

    for move, by_lang in T.items():
        for templates in by_lang.values():
            for tpl in templates:
                for _ in range(renders):
                    slots = {**_fake(rng), "brand": rng.choice(["SBI", "Paytm", "FedEx", "Airtel", "MSEB"]), "police": "Delhi"}
                    text, spans = render(tpl, slots, False, rng)
                    rest = text
                    for code, ev in spans:
                        add(ev, CODES[code])
                        rest = rest.replace(ev, " | ")
                    for chunk in rest.split(" | "):
                        if len(chunk.split()) >= 3:
                            add(chunk, NONE)
    for lines in VICTIM.values():
        for v in lines:
            add(v, NONE)
    for t in extra_negatives or []:
        add(t, NONE)
    return texts, labels


@lru_cache(maxsize=1)
def _encoder(path: str):
    os.environ.setdefault("HF_HUB_OFFLINE", "1" if Path(path).exists() else "0")
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(path, device="cpu")


class SemanticExtractor:
    name = "semantic"

    def __init__(self, model: str | None = None, k: int = 3, margin: float | None = None,
                 min_sim: float = 0.80, extra_negatives: list[str] | None = None):
        path = model or os.getenv("AEGIS_EMBED_MODEL") or (str(DEFAULT_MODEL) if DEFAULT_MODEL.exists()
                                                         else "intfloat/multilingual-e5-small")
        self.enc = _encoder(path)
        self.k = k
        self.margin = margin if margin is not None else float(os.getenv("AEGIS_SEM_MARGIN", "0.02"))
        self.min_sim = min_sim
        self.texts, self.labels = build_bank(extra_negatives=extra_negatives)
        self.bank = self._embed(self.texts)
        self.label_names = sorted(set(self.labels))
        self.idx = {lab: np.array([i for i, l in enumerate(self.labels) if l == lab]) for lab in self.label_names}

    def _embed(self, texts: list[str]) -> np.ndarray:
        return self.enc.encode([f"query: {t}" for t in texts], normalize_embeddings=True,
                               batch_size=64, show_progress_bar=False)

    def scores(self, clause_list: list[str]) -> list[dict[str, float]]:
        if not clause_list:
            return []
        sims = self._embed(clause_list) @ self.bank.T
        out = []
        for row in sims:
            d = {}
            for lab, ix in self.idx.items():
                top = np.sort(row[ix])[-self.k:]
                d[lab] = float(top.mean())
            out.append(d)
        return out

    def hits(self, text: str) -> list[SignalHit]:
        cl = clauses(text)
        found: dict[Signal, SignalHit] = {}
        for c, sc in zip(cl, self.scores(cl)):
            neg = sc[NONE]
            for lab, s in sc.items():
                if lab == NONE or s < self.min_sim or s - neg < self.margin:
                    continue
                sig = Signal(lab)
                conf = round(min(0.85, 0.5 + 5 * (s - neg)), 3)
                if sig not in found or found[sig].confidence < conf:
                    found[sig] = SignalHit(signal=sig, evidence=c, confidence=conf)
        return sorted(found.values(), key=lambda h: h.signal.value)

    def extract(self, text: str, speaker: str = "caller", turn_index: int = 0,
                context: list[str] | None = None) -> SemanticEvent:
        hits = self.hits(text) if speaker == "caller" else []
        sigs = {h.signal for h in hits}
        if Signal.SAFETY_ADVICE in sigs:
            hits = [h for h in hits if h.signal not in (Signal.CREDENTIAL_REQUEST, Signal.SECRECY)]
            sigs = {h.signal for h in hits}
        cands = {SIGNAL_DEFAULT_ACTION[s] for s in sigs if s in SIGNAL_DEFAULT_ACTION}
        action = next((a for a in ACTION_PRIORITY if a in cands), RequestedAction.NONE)
        stages = [SIGNAL_STAGE[s] for s in sigs if SIGNAL_STAGE[s]]
        return SemanticEvent(
            turn_index=turn_index, speaker=speaker,  # type: ignore[arg-type]
            communication_intent=Intent.VICTIM_RESPONSE if speaker == "user" else
            (Intent.REQUEST_ACTION if action is not RequestedAction.NONE else Intent.INFORM),
            manipulation_signals=hits, requested_action=action,
            financial_consequence=ACTION_CONSEQUENCE[action],
            stage=max(stages, key=lambda s: STAGE_INDEX[s], default=None),
            confidence=max((h.confidence for h in hits), default=0.0), source="llm",
        )


class HybridExtractor:
    """Rules (exact, multilingual) + semantic (paraphrase) merged."""

    name = "hybrid"

    def __init__(self, semantic: SemanticExtractor | None = None):
        from .rules import RuleExtractor
        self.rules = RuleExtractor()
        self.sem = semantic or SemanticExtractor()

    def extract(self, text: str, speaker: str = "caller", turn_index: int = 0,
                context: list[str] | None = None) -> SemanticEvent:
        from . import merge
        r = self.rules.extract(text, speaker, turn_index, context)
        s = self.sem.extract(text, speaker, turn_index, context)
        out = merge(r, s)
        return out.model_copy(update={"source": "ensemble", "actor_claim": r.actor_claim,
                                      "communication_intent": r.communication_intent})
