"""Transport tests use httpx.MockTransport only; no real provider is called."""

import httpx
import pytest
from openai import OpenAI

from src.analyzer import Analyzer
from src.config import Settings
from src.llm_client import OpenAICompatibleClient
from src.schemas import AnalysisRequest, Mode, Shell


@pytest.mark.parametrize(
    ("failure", "expected"),
    [("timeout", "超时"), ("network", "无法连接"), (401, "鉴权失败"), (429, "限流"),
     (500, "HTTP 500"), ("bad_json", "格式异常"), ("empty", "没有返回候选"), ("length", "截断")],
)
def test_api_failures_keep_static_findings_and_hide_provider_secrets(failure, expected):
    def respond(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("private-provider-detail", request=request)
        if failure == "network":
            raise httpx.ConnectError("private-provider-detail", request=request)
        if isinstance(failure, int):
            return httpx.Response(failure, json={"error": {"message": "private-provider-detail"}})
        if failure == "empty":
            choices = []
        else:
            choices = [{"index": 0, "finish_reason": "length" if failure == "length" else "stop",
                        "message": {"role": "assistant", "content": "not JSON"}}]
        return httpx.Response(200, json={"id": "mock-id", "object": "chat.completion", "created": 0,
                                        "model": "test-model", "choices": choices})

    settings = Settings(api_key="test-only-placeholder", base_url="https://provider.example.invalid/v1", model_name="test-model", backend="real")
    client = OpenAICompatibleClient(settings)
    client.close()
    client.client = OpenAI(api_key="test-only-placeholder", base_url=settings.base_url, max_retries=0,
                           http_client=httpx.Client(transport=httpx.MockTransport(respond)))
    request = AnalysisRequest(command="rm demo.tmp", source_shell=Shell.BASH, target_shell=Shell.CMD, mode=Mode.RISK)
    try:
        result = Analyzer(settings, client=client).analyze(request)
    finally:
        client.close()
    assert result.model is None
    assert result.backend == "real"
    assert expected in result.error
    assert any(x.code == "deletion" for x in result.static_findings)
    assert "private-provider-detail" not in str(result.model_dump())
    assert "test-only-placeholder" not in str(result.model_dump())
