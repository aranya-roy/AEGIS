# aegis-core: ML design decisions

Owner: AI/ML lead. Scope: privacy gate, semantic extraction, Manipulation State Machine, Scam DNA, ShadowPath, speech model choice, datasets, training, evaluation.
Out of scope (other repos): causal graph storage, risk engine, Reality Pause trigger (aegis-backend); streaming/transport (aegis-realtime); UI (aegis-frontend).

All numbers below come from `python -m aegis_core.evaluation.run` (rules extractor, CPU), full output in `reports/eval_report.json`.

---

## 0. Architecture

```
audio ──ASR──► text turn ──privacy gate──► sanitized turn
                                              │
                    ┌─────────────────────────┼──────────────────────────┐
                    ▼ always (<1 ms)          ▼ within budget (async OK)  │
             rule extractor             LLM extractor (local / Claude)    │
                    └──────────► merge + GROUNDING ◄───────┘               │
                                     │  SemanticEvent (structured JSON)    │
          ┌──────────────────────────┼─────────────────────────┐           │
          ▼                          ▼                         ▼           │
 Manipulation State Machine    Scam DNA fingerprint      ShadowPath        │
   (stage + progress)       (match / novel variant)   (next attacker move) │
          └──────────── AegisEvents + analysis() ──► aegis-backend (graph, risk, Reality Pause)
```

The LLM never outputs `scam = true`. It outputs one `SemanticEvent` per utterance; every downstream decision is computed from those structured fields.

---

## 1. Which speech model?

**Simple:** use Whisper. It is the best free multilingual speech-to-text model and copes with Hindi-English mixing.

**Technical:** `faster-whisper` (CTranslate2) with `large-v3-turbo`, VAD on, `beam_size=1`, no conditioning on previous text (stops hallucinated repetition on silence). Wrapper: `aegis_core/asr.py`; chunking/endpointing is aegis-realtime's job.

| Option | Use when | Tradeoff |
|---|---|---|
| faster-whisper large-v3-turbo (default) | GPU available, mixed EN/HI | ~1.5 GB VRAM int8; weak on Tamil/Telugu |
| faster-whisper small / medium | CPU-only demo laptop | Faster, worse on accents and code-mixing |
| AI4Bharat IndicConformer / IndicWhisper | Indic-heavy calls | Better on Indic, separate model per setup |
| Sarvam / cloud ASR API | No GPU at all | Audio leaves the device, which breaks our privacy story |

**Challenge:** for the 48-hour demo, ASR is not where you win. Pre-record the demo audio, transcribe it once, and replay text so a flaky mic can't kill the pitch. ASR output is lowercase and unpunctuated, which our eval shows hurts name redaction. The privacy gate was rewritten to be case-insensitive because of this.

## 2. Which LLM extracts semantic scam events?

**Simple:** a small open model running locally for live calls, and a strong hosted model in the background and for labelling data.

**Technical:** two tiers behind one interface (`Extractor.extract() -> SemanticEvent`):

| Tier | Model | Latency | Role |
|---|---|---|---|
| T0 | Rule lexicon (EN / Hinglish / Devanagari) | 0.15 ms p50 | Always-on floor; never blocks |
| T1 real-time | Qwen2.5-3B-Instruct (+ LoRA) on vLLM | target ≤ 250 ms/turn, measure | Paraphrase coverage |
| T2 async | Qwen2.5-7B-Instruct (+ LoRA), or Claude (`claude-opus-5-5`) | 1-5 s | Deep re-analysis, teacher labels |

Why Qwen2.5: Apache-2.0, strong JSON/schema following, good Hindi and Hinglish, and 3B/7B sizes fit one 24 GB GPU. Qwen3-8B (already pulled in Ollama on the dev box) works too; turn its thinking mode off for latency. Llama-3.1-8B is weaker on Hindi and has a more restrictive licence.

The Claude backend (`extract/llm_claude.py`) uses structured outputs (`output_config.format` JSON schema) and the server-side refusal fallback (`fallbacks: "default"`). A scam transcript can trip a safety classifier, so a declined request re-runs on a fallback model instead of failing. It only ever receives redacted text.

## 3. Should we fine-tune?

**Simple:** only if the numbers say so.

**Decision rule (fixed before training):** keep a LoRA adapter only if, against the zero-shot base model with few-shot prompting, it gains **≥ 5 points held-out step-recovery F1**, or **≥ 3 points signal F1 on held-out families**, with no worse JSON-validity or grounding rate. Otherwise ship zero-shot plus rules.

**Current evidence:** the rule tier scores 0.886 signal F1 on synthetic data, but recovers only **47% of workflow steps** on hand-written conversations (precision 1.00). Misses are paraphrases ("top up 5000 in your task wallet", "request pe PIN daal dijiye"). An LLM handles these. Run the zero-shot LLM on the same held-out set first; if it already closes the gap, skip training.

**Measured: zero-shot qwen2.5:3b (Q4, Ollama, CPU, few-shot prompt) in the ensemble** (`tools/eval_llm.py`, report `reports/llm_compare_qwen2.5_3b.json`):

| Hand-written held-out set | Rules | Rules + qwen2.5:3b |
|---|---|---|
| Detection AUROC | 0.789 | 1.000 |
| Step recovery P / R | 1.00 / 0.47 | 0.75 / 0.62 |
| Warned by the money turn | 8 / 15 | 14 / 15 |
| Unseen-family scams reaching COMPLIANCE | 2 / 5 | 4 / 5 |
| Benign reaching COMPLIANCE stage | 2 / 6 | 5 / 6 |
| Hinglish OOD sample (20): benign with any signal | 10% | 70% |
| Latency per caller turn (CPU, warm) | 0.2 ms | 8-22 s |

The LLM fixes recall on paraphrases and unseen families, but over-fires on benign payment and refund talk ("consultation fee can be paid at reception"). Scores still rank every benign call below every scam, so the evidence score is usable, but stage-level output is not precise enough to drive intervention. This is the case for the QLoRA run: the SFT set contains benign hard negatives with empty targets, which is exactly the missing behaviour. On a GPU (vLLM, L4) a 3B model runs far below the CPU latency above.

**Precision fixes, designed on dev data only, then evaluated once on the held-out set:**

1. *Plausibility check* (`extract/grounding.py`). The 3B model often quotes real text but attaches the wrong signal ("Sure thing." as ISOLATION, "kal 4 baje hai" as URGENCY). Grounding only checked that the quote exists. Now each signal also needs at least one broad, multilingual cue word in its quote. On dev outputs this cut benign turns with LLM signals from 22 to 6 while scam turns went from 8 to 6 (the two lost were mislabels). It rejects 0.6% of gold evidence quotes (all ASR typos).
2. *Pressure gate* (`state_machine.py`). A request to pay, install or share a code counts at 15% toward the stage until any pressure cue (authority, urgency, threat, isolation, secrecy, channel shift, lure) has appeared; then the rest is added back. Chosen from the definition of the stage, not tuned. `AEGIS_PRESSURE_GATE=0` switches it off. The evidence score is not gated (dev data showed gating only hurt ranking).

| Hand-written held-out set | AUROC | Step P / R / F1 | Warned by money turn | Benign at COMPLIANCE | Unseen families at COMPLIANCE |
|---|---|---|---|---|---|
| rules, gate off | 0.789 | 1.00 / 0.47 / 0.64 | 8 / 15 | 2 / 6 | 2 / 5 |
| rules, gate on | 0.833 | 1.00 / 0.47 / 0.64 | 6 / 15 | 0 / 6 | 1 / 5 |
| rules + qwen2.5:3b, no fixes | 1.000 | 0.75 / 0.62 / 0.68 | 14 / 15 | 5 / 6 | 4 / 5 |
| **rules + qwen2.5:3b + both fixes** | **0.989** | **0.92 / 0.60 / 0.73** | **10 / 15** | **0 / 6** | **3 / 5** |

Report: `reports/llm_heldout_qwen2.5_3b_fixed.json`. With the gate on, rules-only public-test recall at 5% FPR drops (English 0.819 to 0.794, Hinglish 0.728 to 0.687) because rules miss many pressure cues; the LLM tier finds them, which is why the gate costs less there. Recommended default for the demo: rules + LLM with both fixes. Remaining gap (10 / 15 warned) is the case for fine-tuning.

## 4. What dataset do we need?

1. **Synthetic, span-labelled** (`aegis_core/datagen/`): 10 scam workflows plus 5 benign hard-negative workflows, × 3 languages, × real and fictional brands, × 4 channels, × random optional moves, adjacent swaps, small talk, and ASR noise. `python -m aegis_core.cli gen-data` gives 900 conversations and about 5.8k labelled turns in seconds.
2. **Teacher-labelled real text** (`train/label_with_teacher.py`): public scam-call transcripts, news write-ups, and consented/role-played calls, redacted and then labelled by Claude. Outputs that fail grounding are dropped; hand-check about 50 before use.
3. **Hand-written held-out set** (`data/heldout/handwritten.jsonl`, 21 conversations): wording never used in templates, plus **5 scam families the generator never produces** (loan app, OLX "army officer", e-challan link, romance/customs gift, insurance bonus) and 6 benign hard negatives (real bank alert, family rent transfer, delivery code, bill notice…). **This is the number to quote.** Never tune on it; add more before tuning anything.

No bank or customer data is needed anywhere.

## 5. What does one training example look like?

One utterance with up to 4 previous turns of context → one `SemanticEvent` JSON. Loss is computed on the assistant JSON only.

```json
{"messages": [
  {"role": "system", "content": "<SYSTEM_PROMPT from extract/prompts.py>"},
  {"role": "user", "content": "<context>\n[caller] I'm calling from the ICICI security team regarding a transaction on your account ending [ACCOUNT].\n[user] Fine, go ahead.\n[caller] If not verified, all your cards will be frozen today itself.\n</context>\n<current speaker=\"caller\">\nDo not disconnect this call until the verification is complete.\n</current>"},
  {"role": "assistant", "content": "{\"actor_claim\": \"UNKNOWN\", \"communication_intent\": \"REQUEST_ACTION\", \"manipulation_signals\": [{\"signal\": \"ISOLATION\", \"evidence\": \"Do not disconnect this call\", \"confidence\": 1.0}], \"requested_action\": \"STAY_ON_LINE\", \"financial_consequence\": \"LOSS_OF_SUPPORT\", \"stage\": \"ISOLATION\", \"entities\": [], \"confidence\": 1.0}"}
]}
```

Design points:
- Text is already redacted (`[PHONE]`, `[UPI]`, `[NAME]`): the model never learns from or emits PII.
- `evidence` is a verbatim span, which is what makes grounding possible.
- Victim turns are included with empty targets, so the model learns not to over-fire.
- The system prompt is identical at train and inference time. For an adapter, set `AEGIS_LLM_FEWSHOT=0`.

## 6. LoRA or QLoRA?

**QLoRA** (4-bit NF4 base, bf16 LoRA r=16-32 on all linear layers). A 7B model fits on one 24 GB GPU, and quality loss against 16-bit LoRA is negligible for structured extraction. Full fine-tuning is unnecessary: the task is format plus label mapping, not new knowledge.

`train/sft_qlora.py` with `train/configs/qwen2.5-{3b,7b}-qlora.yaml`.

**48-hour plan:** rent **one L4 or A10G (24 GB)**; an A100 40 GB if cheap. About 4.4k training turns × 2 epochs at ≤ 2k tokens is roughly an hour on an A100 and a few hours on an L4 (estimate, measure it). Serve the adapter with `vllm serve Qwen/Qwen2.5-3B-Instruct --enable-lora --lora-modules aegis=runs/.../adapter`.

Alternative real-time tier: `train/train_encoder.py`, a multi-label MuRIL / XLM-R classifier at ~10-30 ms on CPU. It gives no evidence quotes, so it complements the rules rather than replacing the LLM.

## 7. What runs in real time?

Rules (always) + the T1 LLM inside a **latency budget** (`EnsembleExtractor`, default 1500 ms). If the LLM misses the budget, the turn uses the rules result and nothing blocks. State machine, Scam DNA and ShadowPath are count-based and pure Python: **full core pipeline 0.26 ms p50 / 0.38 ms p95 per turn** without the LLM.

**Tried and not enabled: embedding tier** (`extract/semantic.py`, `tools/tune_semantic.py`). Clauses embedded with multilingual-e5-small and matched by k-nearest-neighbour margin against template evidence spans versus non-signal text. Tuned on dev data only (scam-dialogue train split, Hinglish dev half):

| Setting | Dev AUROC | Benign with any signal | Scams with any signal |
|---|---|---|---|
| rules only | 0.948 | 12.0% | 93.7% |
| rules + embedding, best margin (0.01) | 0.950 | 12.0% | 93.9% |
| rules + embedding, margin 0.0 | 0.916 | 21.8% | 94.2% |

The exemplar bank has one or two phrasings per signal, so nearest-neighbour matching does not generalize past the templates and mostly adds false hits. It stays available as `AEGIS_EXTRACTOR=hybrid` but is off by default. Paraphrase coverage needs the LLM tier or a classifier trained on more varied labelled text.

## 8. What runs asynchronously?

The T2 LLM (7B or Claude) re-reads the conversation in the background, and aegis-backend merges its grounded events when they arrive. Teacher labelling, library re-clustering and evaluation are offline.

## 9. How are scam workflows represented?

Three levels (`taxonomy.py`): **Signal** (14 observable cues) → **Step** (9 workflow moves; the first 7 match aegis-frontend's `Step` vocabulary) → **Stage** (6 Manipulation State Machine stages). Stages describe what was *said*, never anyone's mental state.

The state machine is an evidence accumulator over the ordered stages, not a strict automaton, because real scams skip stages (lure-first scams never claim authority).

## 10. How are unseen variants detected?

**Scam DNA** = ordered steps + tactic set + step transitions. It ignores words, brand, language and channel. Similarity is 0.5·LCS order + 0.3·tactic Jaccard + 0.2·transition Jaccard. Known incidents are clustered with average linkage at 0.65, giving 17 patterns. A live call is matched against pattern prototypes with prefix-aware scoring; best match < 0.55 means **emerging variant**.

Result: job-task scams and investment-group scams land in the **same DNA cluster**. Their behaviour (lure → rapport → move to Telegram → payment) is identical; only the bait differs.

## 11. How do we evaluate generalization?

Never random splits; the same templates would leak across them. Use:
- **leave-one-family-out** (Scam DNA novelty and ShadowPath on families absent from the library),
- **leave-one-language / channel / brand-out** (`evaluation/splits.py`; `gen-data` writes `sft_heldout_lang_hi.jsonl` and `sft_heldout_channel_telegram.jsonl`),
- **held-out families for training** (`telecom_sim`, `lottery_fee`, `benign_bill` never appear in `sft_train`),
- **hand-written held-out set** for the headline numbers.

Current results (rules tier):

| Metric | Value |
|---|---|
| Synthetic signal micro P / R / F1 | 0.958 / 0.826 / 0.887 |
| Action / stage accuracy (synthetic) | 0.964 / 0.906 |
| **Held-out step recovery P / R** | **1.00 / 0.47** |
| Held-out detection AUROC (scam vs benign) | 0.789 |
| Warned (stage ≥ COMPLIANCE or ShadowPath → money) by the money turn | 8 / 15 scams |
| Benign reaching COMPLIANCE stage | 2 / 6 (family rent transfer, bill notice) |
| Unseen-family scams reaching COMPLIANCE | 2 / 5 |
| DNA novelty AUROC, leave-family-out | 0.647 |
| ShadowPath top-1 next step: seen / unseen family | 0.63 / 0.49 (top-3 unseen 0.62) |

**Public datasets, out of distribution** (`python -m aegis_core.evaluation.external`, never used for training):

| Dataset | AUROC | Recall at 5% FPR | Scams with any signal |
|---|---|---|---|
| BothBosu/scam-dialogue test (EN, 320 calls, hard negatives), before English fix | 0.935 | 0.775 | 92% |
| same, after adding patterns found on the train split only | 0.941 | 0.819 | 92% |
| Indian Cyber Scam Hinglish, test half (376 unique utterances), before lexicon fix | 0.710 | 0.195 | 52% |
| same test half, after adding patterns found on the dev half only | 0.945 | 0.728 | 93% |

English patterns came from errors on the scam-dialogue train split ("my name is Officer X from the ... Administration", "suspended due to suspicious activity", "confirm your social security number", "if you don't cooperate"). The Hinglish set is split by a hash of the text; only dev-half misses were read when adding patterns (officer self-intros without "se", "FIR ho chuki", "suspect maana", obscene-content accusations). The set is templated, so dev and test share phrasing and the post-fix number is optimistic.

Summary: high precision, low recall on new wording. Novelty detection is only moderate, because many scam families genuinely share structure. The two benign false hits contain a payment instruction but no pressure cue; the backend risk engine should require a pressure signal before escalating (the state machine reports stage, not risk).

## 12. How do we avoid hallucinated scam reasoning?

1. **Constrained decoding**: JSON schema enforced (vLLM `response_format`, Claude structured outputs).
2. **Grounding** (`extract/grounding.py`): a signal survives only if its evidence quote appears in the utterance (exact, or ≥ 80% token overlap with reduced confidence). Entities must occur in the text. The requested action must be supported by a surviving signal. Stage and financial consequence are recomputed deterministically, never taken from the LLM.
3. **Rules floor**: the LLM can add signals but cannot remove rule hits.
4. **Metric**: `grounding_rate` in the eval (1.00 for rules); track the dropped-signal rate per LLM.
5. **No verdicts from the LLM**: it describes utterances; the decision logic downstream is count-based and auditable. Every ShadowPath prediction cites its support ("After urgency → isolation → remote access: 9/15 known incidents went to credential request").

## 13. How do we measure latency?

Per-turn wall-clock in `AegisSession.latencies_ms`; extractor and pipeline p50/p95 in `eval_latency`. Report three numbers separately:
- ASR chunk latency (realtime repo),
- core pipeline (now 0.26 / 0.38 ms),
- LLM tier (`LocalLLMExtractor.last_latency_ms`, plus how often it misses the budget: `EnsembleExtractor.llm_timeouts`).

The product number is **time-to-first-warning before the money turn**, not per-turn ms.

## 14. How do we measure privacy vs utility?

Synthetic data plants known fake PII (names, phones, UPI IDs, account numbers), so leakage can be counted exactly. Run the same eval under three gate modes:

| Mode | PII leak rate | Signal F1 | Held-out AUROC |
|---|---|---|---|
| none (raw) | 94.7% | 0.883 | 0.767 (before English fix) |
| **typed tags** (`[UPI]`, default) | **0.0%** | **0.886** | 0.767 |
| masked (`[REDACTED]`) | 0.0% | 0.873 | 0.767 |

Typed tags cost nothing in detection (they even help slightly: `[PHONE]` is itself a channel-shift cue) and remove all planted PII in this set. Earlier versions leaked ~11% of names on lowercase ASR text before the case-insensitive name rule; that kind of regression is why this check belongs in CI. Caveat: regex redaction will miss unusual names. Upgrade path: a small NER model inside the same gate.

---

## Next steps (ML)

1. Run the zero-shot Qwen2.5-3B/7B with `--extractor ensemble-local` on the held-out set and compare against the table above.
2. If the decision rule in §3 is met, run QLoRA on a rented 24 GB GPU and re-evaluate.
3. Grow the hand-written held-out set to ≥ 60 conversations (each teammate writes 10 in their own words) before claiming any number on stage.
4. Agree on the `LURE` / `TRUST` step extension with frontend and backend; the frontend `Step` type currently drops them.
