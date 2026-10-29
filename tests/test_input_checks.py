import pytest

from src.input_checks import AUTO_SHELL, detect_shell, input_feedback, validate_command_text
from src.schemas import Shell


@pytest.mark.parametrize("command,shell", [
    ('cat "hello world.txt"', Shell.BASH),
    ('Get-Content "hello world.txt"', Shell.POWERSHELL),
    ('echo %PATH%', Shell.CMD),
    ('dir /b', Shell.CMD),
    ('Remove-Item -Recurse C:\\test', Shell.POWERSHELL),
])
def test_shell_detection(command, shell):
    assert detect_shell(command)[0] == shell


def test_ambiguous_and_mixed_input_explain_fallback():
    assert '多种 Shell' in detect_shell('echo hello')[1]
    assert '手动确认' in detect_shell('ls | Select-Object Name')[1]


@pytest.mark.parametrize('command', ['', '  ', '|||', '&&', 'echo \x1b[31m', 'echo \x00'])
def test_invalid_input(command):
    with pytest.raises(ValueError):
        validate_command_text(command)


@pytest.mark.parametrize('command', ['rm -rf /', 'my_custom_tool --flag', '> output.txt', 'echo 中文', 'echo "a|b"'])
def test_valid_or_dangerous_text_is_not_rejected(command):
    validate_command_text(command)


def test_manual_override_and_incomplete_quote_feedback():
    assert input_feedback('ls', 'PowerShell').startswith('手动选择：PowerShell')
    assert '引号未闭合' in input_feedback('cat "file', AUTO_SHELL)


def test_app_auto_selection_and_invalid_input_skip_model():
    from app import run_analysis
    from src.analyzer import Analyzer
    from src.config import Settings
    from src.schemas import AnalysisResult, Mode
    analyzer = Analyzer(Settings())
    report, payload, _ = run_analysis(analyzer, 'Get-Location', AUTO_SHELL, 'Bash', Mode.EXPLAIN.value)
    assert AnalysisResult.model_validate_json(payload).request.source_shell == Shell.POWERSHELL
    assert '自动识别' in report
    class NoCalls:
        def analyze(self, request):
            raise AssertionError('invalid input must not call API')
    report, payload, _ = run_analysis(NoCalls(), '|||', AUTO_SHELL, 'Bash', Mode.EXPLAIN.value)
    assert '输入错误' in report and not payload
