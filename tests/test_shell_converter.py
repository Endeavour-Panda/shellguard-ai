import pytest

from src.analyzer import Analyzer
from src.config import Settings
from src.schemas import AnalysisRequest, Mode, ModelAnalysis, Shell
from src.shell_converter import convert_known_command


@pytest.mark.parametrize(
    ("target", "expected"),
    [(Shell.POWERSHELL, "Write-Output $HOME"), (Shell.CMD, "echo %USERPROFILE%")],
)
def test_bash_home_echo_has_deterministic_conversion(target, expected):
    assert convert_known_command('echo "$HOME"', Shell.BASH, target) == expected


def test_unknown_command_is_not_guessed():
    assert convert_known_command("custom-tool --flag", Shell.BASH, Shell.POWERSHELL) is None


class ConservativeClient:
    backend = "real"

    def analyze(self, request):
        return ModelAnalysis(
            explanation="模型认为跨平台语义存在差异。", converted_command=None,
            risk_level="medium", risk_reasons=["变量语义需核对。"],
            semantic_differences=["路径格式不同。"], validation_suggestions=["核对目标环境。"],
        )


def test_analyzer_uses_reviewed_rule_when_model_returns_null():
    request = AnalysisRequest(command='echo "$HOME"', source_shell=Shell.BASH,
                              target_shell=Shell.POWERSHELL, mode=Mode.CONVERT)
    result = Analyzer(Settings(), client=ConservativeClient()).analyze(request)
    assert result.model.converted_command == "Write-Output $HOME"
    assert result.conversion_source == "rule"


@pytest.mark.parametrize(('command','source','target','expected'), [
    ('ls', Shell.BASH, Shell.POWERSHELL, 'Get-ChildItem'),
    ('pwd', Shell.BASH, Shell.CMD, 'cd'),
    ('cat "quarter report.txt"', Shell.BASH, Shell.POWERSHELL, "Get-Content -LiteralPath 'quarter report.txt'"),
    ('Copy-Item -LiteralPath notes.txt -Destination backup.txt', Shell.POWERSHELL, Shell.BASH, 'cp notes.txt backup.txt'),
    ('type "quarter report.txt"', Shell.CMD, Shell.BASH, "cat 'quarter report.txt'"),
])
def test_literal_conversions(command, source, target, expected):
    assert convert_known_command(command, source, target) == expected


@pytest.mark.parametrize('command', [
    "echo '$HOME'", 'echo "$home"', 'ECHO "$HOME"', 'cat *.txt',
    'cat a.txt; rm -rf /', 'cat $(whoami)', 'cat ../secret', 'cp -r a b',
    'cat "a"b', 'cat a.txt\ncat b.txt', 'echo off', 'cat NUL', 'echo "hello world"',
])
def test_rules_do_not_guess_expansion_options_or_special_names(command):
    assert convert_known_command(command, Shell.BASH, Shell.POWERSHELL) is None
