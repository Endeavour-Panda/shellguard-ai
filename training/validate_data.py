"""Validate reviewed ShellGuard JSONL datasets without loading a model."""

import argparse
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from src.schemas import AnalysisRequest, Mode, ModelAnalysis


class TrainingRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: AnalysisRequest
    answer: ModelAnalysis


def load_records(path: Path) -> list[TrainingRecord]:
    records: list[TrainingRecord] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            record = TrainingRecord.model_validate_json(raw_line)
        except Exception as exc:
            raise ValueError(f"{path}:{line_number} 数据格式无效：{exc}") from None
        if record.request.mode != Mode.CONVERT and record.answer.converted_command is not None:
            raise ValueError(f"{path}:{line_number} 非转换任务不能包含 converted_command")
        if record.request.mode == Mode.CONVERT and record.answer.converted_command is None:
            if record.answer.risk_level.value not in {"high", "critical"}:
                raise ValueError(f"{path}:{line_number} 低/中风险转换样本不应无故拒绝转换")
        records.append(record)
    if not records:
        raise ValueError(f"{path} 没有有效记录")
    return records


def record_key(record: TrainingRecord) -> tuple[str, str, str, str]:
    request = record.request
    return request.command, request.source_shell.value, request.target_shell.value, request.mode.value


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_pair(train_path: Path, eval_path: Path) -> dict:
    train = load_records(train_path)
    eval_records = load_records(eval_path)
    train_keys = [record_key(item) for item in train]
    eval_keys = [record_key(item) for item in eval_records]
    if len(train_keys) != len(set(train_keys)):
        raise ValueError("训练集存在重复请求")
    if len(eval_keys) != len(set(eval_keys)):
        raise ValueError("评估集存在重复请求")
    overlap = set(train_keys) & set(eval_keys)
    if overlap:
        raise ValueError(f"训练集与评估集泄漏：发现 {len(overlap)} 个重复请求")
    return {
        "train_records": len(train),
        "eval_records": len(eval_records),
        "train_sha256": fingerprint(train_path),
        "eval_sha256": fingerprint(eval_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="校验 ShellGuard 微调数据")
    parser.add_argument("--train", type=Path, default=Path("data/shellguard_train.jsonl"))
    parser.add_argument("--eval", type=Path, default=Path("data/shellguard_eval.jsonl"))
    args = parser.parse_args()
    print(json.dumps(validate_pair(args.train, args.eval), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
