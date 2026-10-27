"""OpenAI-compatible transport, strict parsing and clearly labeled offline demo."""

import json
import re
from typing import Protocol

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError
from pydantic import ValidationError

from src.config import ConfigurationError, Settings
from src.examples import EXAMPLES
from src.prompts import build_messages
from src.schemas import AnalysisRequest, MAX_RESPONSE_LENGTH, ModelAnalysis, Mode, RiskLevel


class ModelClientError(RuntimeError):
    """Only sanitized messages may reach the UI; never include provider bodies."""


class Client(Protocol):
    backend: str

    def analyze(self, request: AnalysisRequest) -> ModelAnalysis: ...


def parse_model_response(content: object) -> ModelAnalysis:
    if not isinstance(content, str) or not content.strip():
        raise ModelClientError("模型返回空内容或不支持的内容格式。")
    if len(content) > MAX_RESPONSE_LENGTH:
        raise ModelClientError("模型返回内容过长，已拒绝处理。")
    text = content.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1)

    def unique_object(pairs: list[tuple[str, object]]) -> dict:
        output = {}
        for key, value in pairs:
            if key in output:
                raise ValueError("duplicate JSON field")
            output[key] = value
        return output

    try:
        payload = json.loads(text, object_pairs_hook=unique_object)
        # Strict JSON validation accepts enum strings as JSON has no enum type,
        # while still rejecting stringified numbers, non-list arrays, etc.
        return ModelAnalysis.model_validate_json(json.dumps(payload, ensure_ascii=False), strict=True)
    except (ValueError, TypeError, RecursionError, ValidationError):
        raise ModelClientError("模型返回格式异常：需要完整 JSON、规定的风险等级及全部必填字段；请重试或检查模型兼容性。") from None


class OpenAICompatibleClient:
    backend = "real"

    def __init__(self, settings: Settings):
        if settings.effective_backend != "real":
            raise ConfigurationError("真实客户端需要完整模型配置。")
        self.model = settings.model_name
        self.max_tokens = settings.max_output_tokens
        self.client = OpenAI(
            api_key=settings.api_key.get_secret_value(),
            base_url=settings.base_url,
            timeout=httpx.Timeout(settings.timeout_seconds),
            max_retries=0,
            # Do not forward Authorization through HTTP redirects.
            http_client=httpx.Client(timeout=settings.timeout_seconds, follow_redirects=False),
        )

    def analyze(self, request: AnalysisRequest) -> ModelAnalysis:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=build_messages(request),
                max_tokens=self.max_tokens,
                # No response_format requirement: compatible providers vary.
            )
        except APITimeoutError:
            raise ModelClientError("模型 API 请求超时；请稍后重试，或调整 MODEL_TIMEOUT_SECONDS。") from None
        except AuthenticationError:
            raise ModelClientError("模型 API 鉴权失败；请检查 MODEL_API_KEY 及该密钥的模型访问权限。") from None
        except RateLimitError:
            raise ModelClientError("模型 API 触发限流或额度不足；请稍后重试并检查额度。") from None
        except APIConnectionError:
            raise ModelClientError("无法连接模型 API；请检查网络、证书和 MODEL_BASE_URL。") from None
        except APIStatusError as exc:
            raise ModelClientError(f"模型 API 返回 HTTP {exc.status_code}；请检查接口路径、模型权限和供应商兼容参数。") from None
        except Exception:
            raise ModelClientError("模型 API 响应异常，未获得有效结果；请检查供应商接口兼容性。") from None
        try:
            if not response.choices:
                raise ModelClientError("模型 API 没有返回候选结果。")
            choice = response.choices[0]
            if choice.finish_reason == "length":
                raise ModelClientError("模型输出被长度限制截断，请缩短输入或增加 MODEL_MAX_OUTPUT_TOKENS。")
            if choice.finish_reason not in {"stop", None}:
                raise ModelClientError("模型未正常完成文本分析，可能触发内容过滤或返回了不支持的工具调用。")
            return parse_model_response(choice.message.content)
        except (AttributeError, IndexError, TypeError):
            raise ModelClientError("模型 API 响应结构异常，缺少 choices 或 message.content。") from None

    def close(self) -> None:
        self.client.close()


class MockClient:
    backend = "mock"

    def analyze(self, request: AnalysisRequest) -> ModelAnalysis:
        example = next((item for item in EXAMPLES if item.command_for(request.source_shell) == request.command), None)
        converted = None
        if request.mode == Mode.CONVERT and example and example.command_for(request.source_shell) == request.command:
            converted = example.command_for(request.target_shell)
        elif request.mode == Mode.CONVERT and request.source_shell == request.target_shell:
            converted = request.command
        if request.mode != Mode.CONVERT and example:
            explanation = f"【模拟响应，未调用模型 API】{example.explanation}内置演示未进行实际模型推理，也不能替代真实命令分析。"
        elif request.mode == Mode.CONVERT and example:
            explanation = f"【模拟演示转换，未调用模型 API；预置对照，不代表模型生成或验证】{example.explanation}"
        else:
            explanation = "【模拟响应，未调用模型 API】该输入不在内置演示样例中。离线模式无法提供可靠的逐项语义解释或跨 Shell 转换，请参考静态检测并配置真实 API。"
        return ModelAnalysis(
            explanation=explanation,
            converted_command=converted,
            risk_level=RiskLevel.LOW,
            risk_reasons=["模拟数据的 low 仅为占位，不构成模型风险判断；请查看独立静态规则结果。"],
            semantic_differences=[example.difference if example else "无法确认等价语义，未生成跨 Shell 命令。"],
            validation_suggestions=["先确认源 Shell、目标 Shell、操作系统及版本。", "在隔离测试目录准备示例文件，逐项人工核对；本应用从未执行任何输入或输出命令。"],
        )


def create_client(settings: Settings) -> Client:
    return MockClient() if settings.effective_backend == "mock" else OpenAICompatibleClient(settings)
