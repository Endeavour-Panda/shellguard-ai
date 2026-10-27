"""Evaluate a base model or LoRA adapter on held-out structured outputs."""

import argparse
import json
from pathlib import Path

from src.finetuning import build_training_messages
from src.llm_client import ModelClientError, parse_model_response
from training.metrics import summarize
from training.validate_data import fingerprint, load_records


def parse_args():
    parser = argparse.ArgumentParser(description="评估 ShellGuard 结构化输出")
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--eval-file", type=Path, default=Path("data/shellguard_eval.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-new-tokens", type=int, default=768)
    parser.add_argument("--load-in-4bit", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    except ImportError:
        raise SystemExit("缺少评估依赖：请执行 pip install -r requirements-train.txt") from None
    if not torch.cuda.is_available():
        raise SystemExit("未检测到 CUDA GPU，评估已停止。")

    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    tokenizer_source = str(args.adapter) if args.adapter else args.model
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_source, trust_remote_code=False)
    model_kwargs = {"device_map": "auto", "torch_dtype": dtype, "trust_remote_code": False}
    if args.load_in_4bit:
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=dtype,
            bnb_4bit_use_double_quant=True,
        )
    model = AutoModelForCausalLM.from_pretrained(args.model, **model_kwargs)
    if args.adapter:
        model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()

    rows = []
    records = load_records(args.eval_file)
    for record in records:
        prompt_messages = build_training_messages(record.request, record.answer)[:-1]
        prompt = tokenizer.apply_chat_template(prompt_messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to(model.device)
        with torch.inference_mode():
            generated = model.generate(
                **inputs, max_new_tokens=args.max_new_tokens, do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        new_tokens = generated[0, inputs["input_ids"].shape[1]:]
        raw = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        parsed = None
        error = None
        try:
            parsed = parse_model_response(raw)
        except ModelClientError as exc:
            error = str(exc)
        rows.append({
            "request": record.request.model_dump(mode="json"),
            "expected": record.answer.model_dump(mode="json"),
            "raw_output": raw,
            "parsed": parsed.model_dump(mode="json") if parsed else None,
            "error": error,
        })

    report = {
        "model": args.model,
        "adapter": str(args.adapter) if args.adapter else None,
        "eval_sha256": fingerprint(args.eval_file),
        **summarize(rows),
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "records"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
