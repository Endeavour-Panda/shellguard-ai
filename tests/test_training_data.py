import json

import pytest

from training.validate_data import TrainingRecord, load_records, validate_pair


def test_seed_train_and_eval_sets_validate_and_have_no_overlap():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    report = validate_pair(root / "data/shellguard_train.jsonl", root / "data/shellguard_eval.jsonl")
    assert report["train_records"] == 24
    assert report["eval_records"] == 8
    assert len(report["train_sha256"]) == 64
    assert len(report["eval_sha256"]) == 64


def test_duplicate_and_leaked_examples_are_rejected(tmp_path):
    sample = {
        "request": {"command": "pwd", "source_shell": "Bash", "target_shell": "PowerShell", "mode": "命令解释"},
        "answer": {"explanation": "显示目录", "converted_command": None, "risk_level": "low",
                   "risk_reasons": [], "semantic_differences": [], "validation_suggestions": ["检查路径"]},
    }
    train_path = tmp_path / "train.jsonl"
    eval_path = tmp_path / "eval.jsonl"
    train_path.write_text(json.dumps(sample, ensure_ascii=False) + "\n" + json.dumps(sample, ensure_ascii=False), encoding="utf-8")
    eval_path.write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="重复请求"):
        validate_pair(train_path, eval_path)
    train_path.write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="泄漏"):
        validate_pair(train_path, eval_path)


def test_conversion_splits_are_disjoint_and_match_recorded_hashes():
    from pathlib import Path
    from itertools import combinations
    from training.validate_data import fingerprint
    root = Path(__file__).resolve().parents[1] / 'data/conversion_v3'
    manifest = json.loads((root/'manifest.json').read_text())
    for name in ('train', 'validation', 'test'):
        path = root/f'{name}.jsonl'
        assert fingerprint(path) == manifest[name]['sha256']
        assert len(load_records(path)) == manifest[name]['count']
    for a,b in combinations(('train','validation','test'),2):
        validate_pair(root/f'{a}.jsonl',root/f'{b}.jsonl')
