"""QLoRA fine-tune of a local instruct model on SemanticEvent extraction.

    pip install -e ".[train]"
    python -m aegis_core.cli gen-data --out data/gen          # writes sft_train/sft_val/sft_test jsonl
    python train/sft_qlora.py --config train/configs/qwen2.5-7b-qlora.yaml

Data rows are prompt/completion chat pairs, so TRL computes the loss on the
assistant JSON only. The prompt is the SAME system prompt used at inference
(aegis_core/extract/prompts.py) - do not change one without the other.

Only keep the adapter if it beats the zero-shot base model on
`python -m aegis_core.evaluation.run --extractor local` (see docs/ML_DESIGN.md
section 3 for the decision rule).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import yaml
from datasets import Dataset
from peft import LoraConfig, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer


def load_rows(path: str) -> Dataset:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            msgs = r["messages"]
            rows.append({"prompt": msgs[:-1], "completion": msgs[-1:]})
    return Dataset.from_list(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text())

    tok = AutoTokenizer.from_pretrained(cfg["base_model"])
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        cfg["base_model"], quantization_config=bnb, torch_dtype=torch.bfloat16,
        attn_implementation=cfg.get("attn_implementation", "sdpa"), device_map="auto",
    )
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)

    lora = LoraConfig(
        r=cfg["lora"]["r"], lora_alpha=cfg["lora"]["alpha"], lora_dropout=cfg["lora"]["dropout"],
        target_modules=cfg["lora"].get("target_modules", "all-linear"), task_type="CAUSAL_LM",
    )

    t = cfg["training"]
    sft_kwargs = dict(
        output_dir=cfg["output_dir"],
        num_train_epochs=t["epochs"],
        per_device_train_batch_size=t["batch_size"],
        per_device_eval_batch_size=t["batch_size"],
        gradient_accumulation_steps=t["grad_accum"],
        learning_rate=t["lr"],
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        weight_decay=0.0,
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=t.get("eval_steps", 100),
        save_strategy="steps",
        save_steps=t.get("eval_steps", 100),
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        bf16=True,
        gradient_checkpointing=True,
        report_to=t.get("report_to", "none"),
        seed=t.get("seed", 42),
    )
    # TRL renamed max_seq_length -> max_length; support both.
    fields = getattr(SFTConfig, "__dataclass_fields__", {})
    sft_kwargs["max_length" if "max_length" in fields else "max_seq_length"] = t["max_len"]
    if "completion_only_loss" in fields:
        sft_kwargs["completion_only_loss"] = True

    trainer = SFTTrainer(
        model=model,
        args=SFTConfig(**sft_kwargs),
        train_dataset=load_rows(cfg["data"]["train"]),
        eval_dataset=load_rows(cfg["data"]["val"]),
        processing_class=tok,
        peft_config=lora,
    )
    trainer.train()
    trainer.save_model(cfg["output_dir"] + "/adapter")
    tok.save_pretrained(cfg["output_dir"] + "/adapter")
    print("adapter saved ->", cfg["output_dir"] + "/adapter")
    print("serve: vllm serve", cfg["base_model"], "--enable-lora --lora-modules aegis=" + cfg["output_dir"] + "/adapter")


if __name__ == "__main__":
    main()
