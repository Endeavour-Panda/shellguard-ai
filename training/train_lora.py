"""Train a PEFT LoRA adapter; command text is tokenized, never executed."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.finetuning import LoRAOptions, build_lora_config, build_training_messages, supports_native_bf16
from training.validate_data import load_records, validate_pair


def parse_args():
    parser = argparse.ArgumentParser(description="ShellGuard AI LoRA SFT")
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--train-file", type=Path, default=Path("data/shellguard_train.jsonl"))
    parser.add_argument("--eval-file", type=Path, default=Path("data/shellguard_eval.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("training_outputs/qwen25-05b-shellguard"))
    parser.add_argument("--epochs", type=float, default=5.0)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--max-length", type=int, default=1536)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation", type=int, default=8)
    parser.add_argument("--rank", type=int, default=8)
    parser.add_argument("--alpha", type=int, default=16)
    parser.add_argument("--dropout", type=float, default=0.05)
    parser.add_argument("--load-in-4bit", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--gradient-checkpointing", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


class TokenizedDataset:
    def __init__(self, records, tokenizer, max_length, torch):
        self.items = []
        for record in records:
            messages = build_training_messages(record.request, record.answer)
            prompt = tokenizer.apply_chat_template(messages[:-1], tokenize=False, add_generation_prompt=True)
            full = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
            prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
            full_ids = tokenizer(full, add_special_tokens=False, truncation=True, max_length=max_length)["input_ids"]
            prefix = 0
            for prompt_token, full_token in zip(prompt_ids, full_ids):
                if prompt_token != full_token:
                    break
                prefix += 1
            labels = [-100] * prefix + full_ids[prefix:]
            if not labels or all(label == -100 for label in labels):
                raise ValueError("max-length 太小，模型答案已被全部截断")
            self.items.append({
                "input_ids": torch.tensor(full_ids, dtype=torch.long),
                "attention_mask": torch.ones(len(full_ids), dtype=torch.long),
                "labels": torch.tensor(labels, dtype=torch.long),
            })

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]


class CompletionCollator:
    def __init__(self, pad_token_id, torch):
        self.pad_token_id = pad_token_id
        self.torch = torch

    def __call__(self, features):
        pad_sequence = self.torch.nn.utils.rnn.pad_sequence
        return {
            "input_ids": pad_sequence([x["input_ids"] for x in features], batch_first=True, padding_value=self.pad_token_id),
            "attention_mask": pad_sequence([x["attention_mask"] for x in features], batch_first=True, padding_value=0),
            "labels": pad_sequence([x["labels"] for x in features], batch_first=True, padding_value=-100),
        }


def main() -> None:
    args = parse_args()
    try:
        import torch
        from peft import get_peft_model, prepare_model_for_kbit_training
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, Trainer, TrainingArguments, set_seed
    except ImportError:
        raise SystemExit("缺少训练依赖：请在服务器执行 pip install -r requirements-train.txt") from None

    if not torch.cuda.is_available():
        raise SystemExit("未检测到 CUDA GPU。为避免意外的长时间 CPU 训练，脚本已停止。")
    precision = torch.bfloat16 if supports_native_bf16(torch) else torch.float16

    manifest = validate_pair(args.train_file, args.eval_file)
    set_seed(args.seed)
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=False)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    model_kwargs = {"torch_dtype": precision, "trust_remote_code": False}
    if args.load_in_4bit:
        model_kwargs.update({
            "device_map": "auto",
            "quantization_config": BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=precision,
                bnb_4bit_use_double_quant=True,
            ),
        })
    model = AutoModelForCausalLM.from_pretrained(args.model, **model_kwargs)
    if args.load_in_4bit:
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=args.gradient_checkpointing)
    elif args.gradient_checkpointing:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
    model.config.use_cache = False

    lora_options = LoRAOptions(rank=args.rank, alpha=args.alpha, dropout=args.dropout,
                               target_modules=("q_proj", "k_proj", "v_proj", "o_proj"))
    model = get_peft_model(model, build_lora_config(lora_options))
    model.print_trainable_parameters()

    train_dataset = TokenizedDataset(load_records(args.train_file), tokenizer, args.max_length, torch)
    eval_dataset = TokenizedDataset(load_records(args.eval_file), tokenizer, args.max_length, torch)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    training_args = TrainingArguments(
        output_dir=str(args.output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=args.gradient_accumulation,
        learning_rate=args.learning_rate,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        weight_decay=0.01,
        logging_steps=1,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        bf16=precision == torch.bfloat16,
        fp16=precision == torch.float16,
        optim="paged_adamw_8bit" if args.load_in_4bit else "adamw_torch",
        gradient_checkpointing=args.gradient_checkpointing,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        report_to=[],
        remove_unused_columns=False,
        seed=args.seed,
        data_seed=args.seed,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=CompletionCollator(tokenizer.pad_token_id, torch),
    )
    train_result = trainer.train()
    final_dir = args.output_dir / "final_adapter"
    trainer.save_model(str(final_dir))
    tokenizer.save_pretrained(final_dir)
    manifest.update({
        "base_model": args.model,
        "adapter_dir": str(final_dir),
        "lora": asdict(lora_options),
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "max_length": args.max_length,
        "seed": args.seed,
        "precision": str(precision),
        "load_in_4bit": args.load_in_4bit,
        "torch_version": torch.__version__,
        "cuda_version": torch.version.cuda,
        "train_metrics": train_result.metrics,
        "cuda_device": torch.cuda.get_device_name(0),
    })
    (args.output_dir / "training_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"训练完成，adapter: {final_dir}")


if __name__ == "__main__":
    main()
