"""Application workflow. This module never passes input to a shell."""

from src.config import ConfigurationError, Settings
from src.llm_client import Client, ModelClientError, create_client
from src.schemas import AnalysisRequest, AnalysisResult, Mode, highest_risk
from src.shell_converter import convert_known_command
from src.shell_rules import detect_risks_by_statement


class Analyzer:
    def __init__(self, settings: Settings, client: Client | None = None):
        self.settings = settings
        self.client = client

    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        findings = [*detect_risks_by_statement(request.command, request.source_shell)]
        result = None
        error = None
        backend = "unconfigured"
        conversion_source = "none"
        try:
            if self.client is None:
                self.client = create_client(self.settings)
            client = self.client
            backend = client.backend
            result = client.analyze(request)
            if request.mode != Mode.CONVERT and result.converted_command is not None:
                result = result.model_copy(update={"converted_command": None})
            elif request.mode == Mode.CONVERT:
                known_conversion = convert_known_command(request.command, request.source_shell, request.target_shell)
                if known_conversion is not None:
                    result = result.model_copy(update={"converted_command": known_conversion})
                    conversion_source = "rule"
                elif result.converted_command is not None:
                    conversion_source = "model"
        except ModelClientError as exc:
            error = str(exc)
        except ConfigurationError as exc:
            error = str(exc)
        except Exception as exc:
            # Avoid exposing provider exceptions, environment values or tracebacks in the UI.
            error = "分析失败；请检查配置后重试。"

        if result and request.mode == Mode.CONVERT and result.converted_command:
            findings.extend(detect_risks_by_statement(result.converted_command, request.target_shell, origin="converted"))
        levels = [finding.level for finding in findings]
        if result:
            levels.append(result.risk_level)
        warning = "仅分析文本，从未执行命令。生成命令未经执行验证，请在目标 Shell 的隔离测试目录中人工核对。"
        overall_risk = highest_risk(*levels)
        if overall_risk.value in {"high", "critical"}:
            warning = "高风险警告：请暂停操作，先确认目标范围、变量实际值和备份。" + warning
        return AnalysisResult(
            request=request,
            backend=backend,
            model=result,
            conversion_source=conversion_source,
            static_findings=findings,
            overall_risk=overall_risk,
            error=error,
            warning=warning,
        )
