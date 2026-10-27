# AutoDL LoRA 训练

## 1. 创建 GPU 实例

选择带 NVIDIA CUDA 的 PyTorch 镜像，建议至少 8 GB 显存。默认训练基础模型为 `Qwen/Qwen2.5-0.5B-Instruct`，不需要在 AutoDL 上提供 DashScope API Key。若所在网络无法访问 Hugging Face，先按 AutoDL 支持的方式配置模型镜像或预下载模型目录，再将本地目录传入 `--model`。

## 2. 上传项目并检查 GPU

在 AutoDL 的 Jupyter 终端或已配置密钥的 SSH 会话中进入项目根目录：

```bash
cd /root/ShellGuard-AI
nvidia-smi
python3 --version
```

将本项目 `training/`、`data/`、`src/`、`requirements.txt` 和 `requirements-train.txt` 一并上传。路径可以按服务器上的实际项目目录调整。

## 3. 安装并校验

```bash
python3 -m venv .venv-train
source .venv-train/bin/activate
python -m pip install -U pip
python -m pip install -r requirements-train.txt
python -m training.validate_data
```

数据校验应报告 24 条训练、8 条评估记录，并显示两个 SHA256。训练和评估请求必须无交叉；若你扩充数据，应保持独立留出集。

## 4. 先测基础模型，再微调

```bash
python -m training.evaluate \
  --model Qwen/Qwen2.5-0.5B-Instruct \
  --output training_outputs/base_eval.json

python -m training.train_lora \
  --model Qwen/Qwen2.5-0.5B-Instruct \
  --train-file data/shellguard_train.jsonl \
  --eval-file data/shellguard_eval.jsonl \
  --output-dir training_outputs/qwen25-05b-shellguard

python -m training.evaluate \
  --model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter training_outputs/qwen25-05b-shellguard/final_adapter \
  --eval-file data/shellguard_eval.jsonl \
  --output training_outputs/lora_eval.json
```

默认启用 4-bit NF4 QLoRA、rank 8、alpha 16、dropout 0.05、学习率 2e-4、5 epoch、序列长度 1536、micro-batch 1 和梯度累积 8。显存不足时先减小 `--max-length` 或关闭 4-bit 前确认显存充足；不要在没有检查显存的情况下扩大 batch。

## 5. 保存实验结果

保留 `base_eval.json`、`lora_eval.json`、`training_manifest.json`、完整训练日志和 GPU 型号。评估指标包括结构化 JSON 有效率、风险等级准确率、转换命令精确匹配率。8 条评估数据只能作为管线和初步效果检查，不足以支撑统计显著或生产质量结论。

训练不会执行数据集中的 Shell 命令。种子数据只是小型人工编写样例，正式结论应先扩充并人工复核数据，特别检查危险命令是否被训练为拒绝执行、语义解释和必要验证提示。
