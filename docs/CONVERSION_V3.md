# 转换改进与复现

第三轮使用 Qwen2.5-1.5B-Instruct 基础模型和普通 FP16 LoRA。此前线上版本为 Qwen2.5-0.5B-Instruct + 第二轮 adapter。本轮针对常见命令转换扩充数据；已完成微调及同批题评估。

## 改进内容

- 合成训练集从原来 24 条扩充到 197 条，18 条验证选择 checkpoint，32 条保留测试检验有限语法内的新参数。详见 data/conversion_v3/README.md。
- 常见字面量命令采用明确规则：列目录、当前目录、简单输出、读取文件、复制、移动、创建目录、HOME/PATH。覆盖 Bash、PowerShell、CMD；输入中的未知选项、管道、变量展开、通配符、路径分隔符不由这些规则猜测。
- 修复 Bash 单引号 `$HOME` 被误当成变量展开及大小写不敏感的问题。对带空格文件名使用目标 Shell 的引号。
- 规则结果会标记“确定性内置规则”，并说明输出格式、隐藏项、编码、覆盖交互等差异；没有执行或声称验证了命令。
- 模型原始成绩与应用规则修正成绩分开计算。模型 JSON 无效时仍记为失败，不用规则掩盖模型失败。

## 训练

在已安装训练依赖的 GPU 环境：

```bash
python -m training.build_conversion_data
python -m training.train_lora \
  --model /root/autodl-tmp/models/Qwen2.5-1.5B-Instruct \
  --train-file data/conversion_v3/train.jsonl \
  --eval-file data/conversion_v3/validation.jsonl \
  --output-dir training_outputs/autodl2080ti-v3/lora \
  --epochs 5 --no-load-in-4bit --max-length 1536
```

RTX 2080 Ti 11GB；FP16，LoRA rank=8、alpha=16、dropout=0.05；目标模块 q_proj/k_proj/v_proj/o_proj；batch=1，梯度累积=8，学习率 2e-4，cosine，warmup=0.05，seed=42，梯度检查点开启。约 218 万可训练参数，占 0.141%。这不是 4-bit QLoRA。

## 评估

```bash
python -m training.evaluate \
  --model /root/autodl-tmp/models/Qwen2.5-1.5B-Instruct \
  --adapter training_outputs/autodl2080ti-v3/lora/final_adapter \
  --eval-file data/conversion_v3/test.jsonl \
  --output training_outputs/autodl2080ti-v3/test_lora.json \
  --max-new-tokens 1024 --no-load-in-4bit
```

旧模型需使用相同 test.jsonl 和 max-new-tokens，再用 `training.compare_conversion` 对比。保留原始输出、解析结果、标准答案和文件哈希。严格字符串匹配不会把所有语义近似写法视为正确；也不能以合成测试成绩推断真实复杂脚本的准确率。

课堂展示建议：`ls` 转换、`cat "quarter report.txt"` 转换、含空格文件名的复制、`rm -rf /` 风险分析，以及结果 JSON 下载。不要实际执行危险命令。

## 实测结果

在 32 条保留的合成转换测试上：

| 指标 | 原 0.5B + v2 LoRA | 新 1.5B + v3 LoRA |
|---|---:|---:|
| 有效 JSON | 29/32（90.625%） | 32/32（100%） |
| 模型原始转换严格匹配 | 2/32（6.25%） | 7/32（21.875%） |
| 两者都加上本轮规则后严格匹配 | 29/32（90.625%） | 32/32（100%） |

**32/32 是应用组合方案的有限场景成绩，不是大模型本身的转换准确率。** 模型仍会错误改写带空格的文件名；本轮规则会对明确支持的语法保留参数及目标引号。测试中的所有命令均处于规则支持范围，不能用此数字说明未知语法也能正确转换。

原来的 8 条验证题另作历史回归：新模型有效 JSON 8/8、风险标签匹配 7/8、原始转换严格匹配 1/3；旧 v2 分别为 7/8、4/8、0/3。旧评估生成上限为 1536，本轮为 1024，因此历史结果不是完全受控对比。真正同配置的比较是上面 32 条题（两者均为 1024）。没有据保留测试成绩继续调参或重新训练。

FP16 LoRA 实际训练 381.28 秒；第 5 epoch 验证损失约 0.01464，最终选择 checkpoint-125。低验证损失不能代替生成正确率。原始模型输出见 artifacts/autodl/autodl2080ti-v3/。
