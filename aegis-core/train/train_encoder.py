"""Fast multi-label signal classifier (alternative real-time tier).

A multilingual encoder tags each utterance with the 14 manipulation
signals. ~10-30 ms/turn on CPU after ONNX export, no evidence quotes (so
it complements the rule tier rather than replacing the LLM tier).

    python train/train_encoder.py --train data/gen/sft_train.jsonl --val data/gen/sft_val.jsonl \
        --model google/muril-base-cased --out runs/muril-signals

MuRIL is pre-trained on Indian languages incl. transliterated (Hinglish)
text; xlm-roberta-base is the safe fallback.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import torch
from datasets import Dataset
from transformers import (
    AutoModelForSequenceClassification, AutoTokenizer, Trainer, TrainingArguments,
)

SIGNALS = [
    "AUTHORITY_CLAIM", "TRUST_BUILDING", "REWARD_LURE", "URGENCY", "THREAT", "CHANNEL_SHIFT",
    "ISOLATION", "SECRECY", "VERIFICATION_DISCOURAGEMENT", "REMOTE_ACCESS", "CREDENTIAL_REQUEST",
    "PERSONAL_INFO_REQUEST", "PAYMENT_REQUEST", "SAFETY_ADVICE",
]


def load(path: str) -> Dataset:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            user = r["messages"][1]["content"]
            text = user.split("<current", 1)[1].split(">", 1)[1].rsplit("</current>", 1)[0].strip()
            target = json.loads(r["messages"][2]["content"])
            present = {h["signal"] for h in target["manipulation_signals"]}
            rows.append({"text": text, "labels": [float(s in present) for s in SIGNALS]})
    return Dataset.from_list(rows)


def metrics(pred) -> dict:
    logits, labels = pred
    p = (1 / (1 + np.exp(-logits))) > 0.5
    tp = (p & (labels == 1)).sum()
    fp = (p & (labels == 0)).sum()
    fn = (~p & (labels == 1)).sum()
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {"micro_p": prec, "micro_r": rec, "micro_f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True)
    ap.add_argument("--val", required=True)
    ap.add_argument("--model", default="google/muril-base-cased")
    ap.add_argument("--out", default="runs/encoder-signals")
    ap.add_argument("--epochs", type=int, default=4)
    args = ap.parse_args()

    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model, num_labels=len(SIGNALS), problem_type="multi_label_classification",
        id2label=dict(enumerate(SIGNALS)), label2id={s: i for i, s in enumerate(SIGNALS)},
    )

    def enc(b):
        return tok(b["text"], truncation=True, max_length=128)

    train, val = load(args.train).map(enc, batched=True), load(args.val).map(enc, batched=True)
    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=args.out, num_train_epochs=args.epochs, learning_rate=3e-5,
            per_device_train_batch_size=32, per_device_eval_batch_size=64,
            eval_strategy="epoch", save_strategy="epoch", load_best_model_at_end=True,
            metric_for_best_model="micro_f1", bf16=torch.cuda.is_available(), report_to="none",
        ),
        train_dataset=train, eval_dataset=val, processing_class=tok, compute_metrics=metrics,
    )
    trainer.train()
    trainer.save_model(args.out + "/best")
    print(trainer.evaluate())


if __name__ == "__main__":
    main()
