"""Independent, optional LoRA preparation for a future AutoDL environment.

Importing this module does not load torch, download a model, create data or train.
The serving application has no dependency on PEFT/Transformers.
"""

import json
from dataclasses import dataclass

from src.prompts import build_messages
from src.schemas import AnalysisRequest, ModelAnalysis


@dataclass(frozen=True)
class LoRAOptions:
    rank: int = 8
    alpha: int = 16
    dropout: float = 0.05
    target_modules: tuple[str, ...] = ("q_proj", "v_proj")

    def __post_init__(self):
        if self.rank < 1 or self.alpha < 1 or not 0 <= self.dropout < 1:
            raise ValueError("LoRA rank/alpha 需为正数，dropout 需位于 [0, 1)。")
        if not self.target_modules or any(not x.strip() for x in self.target_modules):
            raise ValueError("请根据基础模型提供有效 target_modules。")


def build_lora_config(options: LoRAOptions | None = None):
    """Create only PEFT configuration; optional packages belong on AutoDL."""
    options = options or LoRAOptions()
    try:
        from peft import LoraConfig, TaskType
    except ImportError:
        raise RuntimeError("LoRA 为预留模块；请在后续训练环境单独安装 peft、transformers 和匹配 CUDA 的 torch。") from None
    return LoraConfig(
        r=options.rank, lora_alpha=options.alpha, lora_dropout=options.dropout,
        target_modules=list(options.target_modules), bias="none", task_type=TaskType.CAUSAL_LM,
    )


def build_training_messages(request: AnalysisRequest, reviewed_answer: ModelAnalysis) -> list[dict[str, str]]:
    """Format one human-reviewed record; performs no file writes or training."""
    if request.mode.value != "跨 Shell 转换" and reviewed_answer.converted_command is not None:
        raise ValueError("非转换任务的人工审核答案不能包含转换命令。")
    return [*build_messages(request), {"role": "assistant", "content": json.dumps(reviewed_answer.model_dump(mode="json"), ensure_ascii=False)}]


def supports_native_bf16(torch) -> bool:
    """Exclude software emulation on pre-Ampere GPUs such as RTX 2080 Ti."""
    return torch.cuda.get_device_capability(0)[0] >= 8 and torch.cuda.is_bf16_supported()
