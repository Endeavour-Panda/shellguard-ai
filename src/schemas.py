"""Validated request, model response and combined result contracts."""

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

MAX_COMMAND_LENGTH = 8000
MAX_RESPONSE_LENGTH = 64000
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]
TextList = Annotated[list[Text], Field(max_length=30)]


class Shell(str, Enum):
    BASH = "Bash"
    POWERSHELL = "PowerShell"
    CMD = "CMD"


class Mode(str, Enum):
    EXPLAIN = "命令解释"
    CONVERT = "跨 Shell 转换"
    RISK = "风险分析"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


RISK_ORDER = {level: index for index, level in enumerate(RiskLevel)}
RISK_LABELS = {RiskLevel.LOW: "低", RiskLevel.MEDIUM: "中", RiskLevel.HIGH: "高", RiskLevel.CRITICAL: "严重"}


def highest_risk(*levels: RiskLevel) -> RiskLevel:
    return max(levels, key=RISK_ORDER.__getitem__, default=RiskLevel.LOW)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalysisRequest(StrictModel):
    command: str = Field(min_length=1, max_length=MAX_COMMAND_LENGTH)
    source_shell: Shell
    target_shell: Shell
    mode: Mode

    @field_validator("command")
    @classmethod
    def validate_command(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("请输入需要分析的命令")
        if "\x00" in value:
            raise ValueError("命令不能包含 NUL 字符")
        return value  # Preserve quoting, indentation and literal whitespace.


class ModelAnalysis(StrictModel):
    explanation: Text
    converted_command: str | None = Field(max_length=8000)
    risk_level: RiskLevel
    risk_reasons: TextList
    semantic_differences: TextList
    validation_suggestions: Annotated[list[Text], Field(min_length=1, max_length=30)]

    @field_validator("converted_command")
    @classmethod
    def nonblank_conversion(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or "\x00" in value):
            raise ValueError("转换命令需为非空文本或 null")
        return value


class RuleFinding(StrictModel):
    code: str
    level: RiskLevel
    reason: str
    suggestion: str
    origin: Literal["input", "converted"] = "input"
    statement_index: int | None = Field(default=None, ge=1)


class AnalysisResult(StrictModel):
    request: AnalysisRequest
    backend: Literal["mock", "real", "local", "unconfigured"]
    model: ModelAnalysis | None
    conversion_source: Literal["model", "rule", "none"] = "none"
    static_findings: list[RuleFinding]
    overall_risk: RiskLevel
    error: str | None = None
    warning: str = "仅分析文本，从未执行命令。生成命令未经执行验证，请在目标 Shell 的隔离测试目录中人工核对。"
