import pytest

from src.analyzer import Analyzer
from src.config import ConfigurationError, Settings
from src.schemas import AnalysisRequest, Mode, RiskLevel, Shell


def request(command="rm -rf /", mode=Mode.RISK):
    return AnalysisRequest(command=command, source_shell=Shell.BASH, target_shell=Shell.POWERSHELL, mode=mode)


def test_auto_backend_only_selects_mock_if_every_model_setting_is_absent():
    assert Settings().effective_backend == "mock"
    with pytest.raises(ConfigurationError):
        Settings(api_key="partial").effective_backend


def test_remote_http_endpoints_are_rejected():
    with pytest.raises(ValueError, match="HTTPS"):
        Settings(base_url="http://api.example.invalid/v1")


def test_analyzer_keeps_static_critical_risk_separate_from_mock_judgment():
    result = Analyzer(Settings()).analyze(request())
    assert result.backend == "mock"
    assert result.model.risk_level == RiskLevel.LOW
    assert result.overall_risk == RiskLevel.CRITICAL
    assert any(item.origin == "input" and item.code == "broad_delete" for item in result.static_findings)


def test_incomplete_configuration_is_reported_without_leaking_secret():
    result = Analyzer(Settings(api_key="top-secret-value")).analyze(request("ls"))
    assert "配置不完整" in result.error
    assert "top-secret-value" not in str(result.model_dump())


class TranslationClient:
    backend = "mock"

    def analyze(self, request):
        from src.schemas import ModelAnalysis
        return ModelAnalysis(explanation="test", converted_command="rm -rf /", risk_level="low", risk_reasons=[],
                             semantic_differences=[], validation_suggestions=["test"])


def test_analyzer_scans_model_translation_and_tracks_its_origin():
    result = Analyzer(Settings(), client=TranslationClient()).analyze(request("ls", Mode.CONVERT))
    finding = next(item for item in result.static_findings if item.code == "broad_delete")
    assert finding.origin == "converted"
    assert result.overall_risk == RiskLevel.CRITICAL
