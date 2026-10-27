#!/usr/bin/env bash
# Run on the GPU server; no SSH password or API credential is stored here.
set -Eeuo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
SERVER_PYTHON="${SERVER_PYTHON:-$PROJECT_DIR/.venv-server/bin/python}"
MODEL_ID="${MODEL_ID:-Qwen/Qwen2.5-0.5B-Instruct}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export GRADIO_ANALYTICS_ENABLED=False

require_python() {
    if [[ ! -x "$SERVER_PYTHON" ]]; then
        echo "缺少服务器虚拟环境，请先运行 bash scripts/school_server.sh setup" >&2
        exit 1
    fi
}

check_cuda() {
    "$SERVER_PYTHON" - <<'PY'
import torch
if not torch.cuda.is_available():
    raise SystemExit('CUDA 不可用：请核对 NVIDIA 驱动与当前环境的 PyTorch CUDA 版本。')
free, total = torch.cuda.mem_get_info(0)
print({'torch': torch.__version__, 'cuda': torch.version.cuda,
       'gpu': torch.cuda.get_device_name(0),
       'free_GiB': round(free / 2**30, 2), 'total_GiB': round(total / 2**30, 2)})
if free < 6 * 2**30:
    raise SystemExit('可用显存不足 6 GiB，停止启动任务。请等待空闲 GPU 或用 CUDA_VISIBLE_DEVICES 选择其他 GPU。')
PY
}

case "${1:-check}" in
    check)
        hostname
        command -v python3
        python3 --version
        nvidia-smi
        df -h "$PROJECT_DIR"
        if [[ -x "$SERVER_PYTHON" ]]; then check_cuda; fi
        ;;
    setup)
        # Run this after selecting the school's existing CUDA/PyTorch environment.
        # Reuse installed CUDA torch if it satisfies requirements; do not modify it.
        python3 -m venv --system-site-packages .venv-server
        "$SERVER_PYTHON" -m pip install -r requirements-train.txt
        "$SERVER_PYTHON" -m training.validate_data
        check_cuda
        ;;
    train)
        require_python
        check_cuda
        "$SERVER_PYTHON" -m training.validate_data
        RUN_DIR="${RUN_DIR:-$PROJECT_DIR/training_outputs/server-$(date -u +%Y%m%dT%H%M%SZ)}"
        mkdir -p "$RUN_DIR" "$PROJECT_DIR/training_outputs"
        # Protect against two simultaneous experiment pipelines in this checkout.
        exec 9>"$PROJECT_DIR/training_outputs/server-training.lock"
        flock -n 9 || { echo '本项目已有训练流水线运行。' >&2; exit 1; }
        exec > >(tee -a "$RUN_DIR/pipeline.log") 2>&1
        echo "实验目录：$RUN_DIR"
        nvidia-smi
        "$SERVER_PYTHON" -m pip freeze > "$RUN_DIR/environment.txt"
        git rev-parse HEAD > "$RUN_DIR/code_commit.txt"
        git diff > "$RUN_DIR/code_changes.patch"
        "$SERVER_PYTHON" -m training.evaluate --model "$MODEL_ID" \
            --no-load-in-4bit --max-new-tokens 1536 --output "$RUN_DIR/base_eval.json"
        "$SERVER_PYTHON" -m training.train_lora --model "$MODEL_ID" \
            --no-load-in-4bit --epochs 5 --output-dir "$RUN_DIR/lora"
        "$SERVER_PYTHON" -m training.evaluate --model "$MODEL_ID" \
            --adapter "$RUN_DIR/lora/final_adapter" --no-load-in-4bit \
            --max-new-tokens 1536 --output "$RUN_DIR/lora_eval.json"
        "$SERVER_PYTHON" -m training.compare --base "$RUN_DIR/base_eval.json" \
            --tuned "$RUN_DIR/lora_eval.json" --output "$RUN_DIR/comparison.md"
        printf '\n实验结束。启动微调 Web：\nLOCAL_MODEL=%q LOCAL_ADAPTER=%q bash scripts/school_server.sh serve\n' \
            "$MODEL_ID" "$RUN_DIR/lora/final_adapter"
        ;;
    serve)
        require_python
        check_cuda
        if [[ -n "${LOCAL_ADAPTER:-}" && ! -f "$LOCAL_ADAPTER/adapter_config.json" ]]; then
            echo 'LOCAL_ADAPTER 目录缺少 adapter_config.json，请填写成功训练生成的 final_adapter 路径。' >&2
            exit 1
        fi
        export SHELLGUARD_BACKEND=local
        export LOCAL_MODEL="${LOCAL_MODEL:-$MODEL_ID}"
        export LOCAL_ADAPTER="${LOCAL_ADAPTER:-}"
        export APP_HOST="${APP_HOST:-127.0.0.1}"
        export APP_PORT="${APP_PORT:-7860}"
        export MODEL_MAX_OUTPUT_TOKENS="${MODEL_MAX_OUTPUT_TOKENS:-1536}"
        exec "$SERVER_PYTHON" app.py
        ;;
    *)
        echo '用法：bash scripts/school_server.sh {check|setup|train|serve}' >&2
        exit 2
        ;;
esac
