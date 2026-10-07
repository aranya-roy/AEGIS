# aegis-core

AI/ML intelligence layer of **AEGIS** (Adaptive Engine for Graph-based Intelligence & Scam-interruption), RAKSHAM AI Cybersecurity Hackathon, IIT Delhi, PS-02.

> Scammers don't steal money first. They steal the decision.

Given a live call/chat turn, aegis-core removes PII, extracts **structured semantic events** (never `scam = true`), tracks the **manipulation stage**, matches the **Scam DNA** of the workflow against known patterns (or flags a new variant), and predicts the attacker's **next move** (ShadowPath).

Design rationale and answers to every model / data / training / eval question: **[docs/ML_DESIGN.md](docs/ML_DESIGN.md)**.

## What this repo emits

The aegis-core rows of the shared event contract (aegis-frontend README):

| Event | Produced here |
|---|---|
| `transcript`, `privacy` | privacy gate (`privacy.py`) |
| `signal` | semantic extraction (`extract/`) |
| `stage` | Manipulation State Machine (`state_machine.py`) |
| `scam_dna` | Scam DNA (`dna.py`) |
| `shadowpath` | ShadowPath (`shadowpath.py`) |

`graph_node`, `risk`, `reality_pause` are aegis-backend's. For those, `AegisSession.analysis()` returns structured state: per-turn `SemanticEvent`s (actor → tactic → instruction → requested action → financial consequence), stage scores, DNA fingerprint and match, and the ShadowPath prediction with support. `taxonomy.SIGNAL_WEIGHT` / `SIGNAL_SEVERITY` are exported for reuse.

## Quick start

```bash
pip install -e ".[dev]"          # core needs only pydantic + httpx
python -m aegis_core.cli demo scenarios/bank_scam.json        # AegisEvent JSON lines
python -m aegis_core.cli demo scenarios/bank_scam.json --analysis
python -m aegis_core.cli extract "Sir AnyDesk install karke code bata dijiye"
pytest -q
python -m aegis_core.evaluation.run                           # writes reports/eval_report.json
```

## Integration (for aegis-realtime / aegis-backend)

```python
from aegis_core.pipeline import AegisSession

session = AegisSession()                       # one per call/chat
events = session.feed({"speaker": "caller", "text": "...", "at": 4000})  # list[dict] AegisEvents
state = session.analysis()                     # structured state for graph / risk / Reality Pause
```

- `feed()` is synchronous and takes ~0.3 ms with the rules extractor; call it from the realtime worker per finalized utterance.
- Raw text never leaves `feed()`: every emitted `transcript.text` and evidence string is already redacted.
- Library for `/patterns`: `python -m aegis_core.cli export-library --out data/library.json` (incidents, patterns, and `frontend_incidents` in `{id,label,surface,steps[]}` shape).
- Audio: `aegis_core.asr.transcribe_chunk(audio)` returns turns ready for `feed()`.

## Extractor tiers

Selected with `AEGIS_EXTRACTOR`:

| Value | What | Needs |
|---|---|---|
| `rules` (default) | multilingual lexicon, exact evidence spans | nothing |
| `local` / `ensemble-local` | OpenAI-compatible endpoint (vLLM, Ollama) + grounding; ensemble keeps rules and caps LLM latency (`AEGIS_LLM_BUDGET_MS`) | `AEGIS_LLM_BASE_URL`, `AEGIS_LLM_MODEL`, `AEGIS_LLM_TIMEOUT_S`; set `AEGIS_LLM_FEWSHOT=0` for a fine-tuned adapter. The LLM is called on caller turns only |
| `claude` / `ensemble-claude` | Claude structured outputs + grounding; async / teacher tier | `pip install -e ".[claude]"`, API key; `AEGIS_CLAUDE_MODEL` (default `claude-opus-5-5`), `AEGIS_CLAUDE_EFFORT` |

## Data and training

```bash
python -m aegis_core.cli gen-data --out data/gen   # 900 synthetic convs -> sft_train/val/test + language/channel holdouts
python train/label_with_teacher.py --in data/raw/transcripts.jsonl --out data/gen/sft_teacher.jsonl
pip install -e ".[train]" && python train/sft_qlora.py --config train/configs/qwen2.5-3b-qlora.yaml
python train/train_encoder.py --train data/gen/sft_train.jsonl --val data/gen/sft_val.jsonl
```

Public OOD test: `python -m aegis_core.evaluation.fetch_external && python -m aegis_core.evaluation.external`.

`data/heldout/handwritten.jsonl` is the real test set (new wording + 5 unseen scam families + benign hard negatives). Never tune on it.

## Current results (rules tier, CPU)

Synthetic signal F1 0.887; public English scam-dialogue AUROC 0.941 and Hinglish call AUROC 0.945 (out of distribution); **held-out step recovery precision 1.00, recall 0.47**; held-out AUROC 0.79; core pipeline 0.26 ms p50 per turn; planted-PII leak rate 0.0% with typed redaction, at no detection cost. With the local LLM tier (qwen2.5:3b) plus the plausibility check and pressure gate: held-out AUROC 0.989, step F1 0.73 (P 0.92, R 0.60), no benign call reaching the compliance stage. Details and caveats: [docs/ML_DESIGN.md §11-14](docs/ML_DESIGN.md).

## Layout

```
aegis_core/
  taxonomy.py        Signal / Step / Stage vocabulary (Step matches frontend)
  schema.py          SemanticEvent + aegis-core AegisEvent models
  privacy.py         typed PII redaction (EN/HI, ASR-robust)
  extract/           rules, local LLM, Claude, grounding, ensemble, shared prompt
  state_machine.py   Manipulation State Machine
  dna.py             Scam DNA fingerprint, similarity, clustering, novelty
  shadowpath.py      next-step prediction (variable-order Markov + DNA prior)
  library.py         incident library bootstrap / export
  pipeline.py        AegisSession
  asr.py             faster-whisper wrapper
  datagen/           span-annotated templates + generator
  evaluation/        metrics, splits, run.py
train/               QLoRA SFT, encoder classifier, teacher labelling, configs
data/heldout/        hand-written held-out conversations
scenarios/           demo transcripts
reports/             eval output
```
