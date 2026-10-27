"""Compare actual evaluation artifacts; never generate synthetic scores."""
import argparse
import json
from pathlib import Path
from training.metrics import summarize


def compare(base, tuned):
    if base["model"] != tuned["model"]:
        raise ValueError("两个结果的基础模型必须相同")
    if base.get("adapter") or not tuned.get("adapter"):
        raise ValueError("请依次提供基础模型与 LoRA adapter 的评估结果")
    signature = lambda report: [(row["request"], row["expected"]) for row in report["records"]]
    if signature(base) != signature(tuned):
        raise ValueError("两次评估必须使用相同顺序、相同标注的评估集")
    before, after = summarize(base["records"]), summarize(tuned["records"])
    lines = ["# 基础模型与 LoRA 评估对比", "", f"样本数：{before['total']}，转换样本数：{before['conversion_total']}。", "",
             "| 指标 | 基础模型 | LoRA | 差值（百分点） |", "| --- | ---: | ---: | ---: |"]
    for key, label in [("valid_json_rate", "JSON 有效率"), ("risk_accuracy", "风险等级准确率"),
                       ("conversion_exact_match", "转换精确匹配率")]:
        left, right = before[key], after[key]
        if left is None:
            lines.append(f"| {label} | 不适用 | 不适用 | — |")
        else:
            lines.append(f"| {label} | {left:.2%} | {right:.2%} | {(right-left)*100:+.2f} |")
    lines.extend(["", "格式无效的输出按错误计入总样本。精确匹配不代表命令已执行或语义已验证。",
                  "若评估集参与训练过程中的模型选择，则这些结果属于验证集结果，不能代替独立测试集结论。"])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="比较基础模型与微调模型的真实评估文件")
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--tuned", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(json.loads(args.base.read_text(encoding="utf-8")), json.loads(args.tuned.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
