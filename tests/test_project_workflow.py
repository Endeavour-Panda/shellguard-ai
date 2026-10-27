import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from app import analyze_session, export_result, launch_auth, restore_history
from src.analyzer import Analyzer
from src.config import ConfigurationError, Settings
from src.llm_client import create_client
from src.schemas import AnalysisRequest
from training.compare import compare
from training.metrics import summarize


def request():
    return AnalysisRequest(command='ls', source_shell='Bash', target_shell='PowerShell', mode='跨 Shell 转换')


def test_history_is_bounded_isolated_and_restores_original_request():
    analyzer = Analyzer(Settings(backend='mock'))
    previous = []
    for _ in range(22):
        output = analyze_session(analyzer, 'ls', 'Bash', 'PowerShell', '跨 Shell 转换', previous)
        assert output[3] is not previous
        previous = output[3]
    assert len(previous) == 20
    assert restore_history('0', previous)[:4] == ('ls', 'Bash', 'PowerShell', '跨 Shell 转换')
    assert len(restore_history(None, previous)) == 10
    other = analyze_session(analyzer, 'pwd', 'Bash', 'CMD', '命令解释', [])
    assert len(other[3]) == 1
    invalid = analyze_session(analyzer, ' ', 'Bash', 'CMD', '命令解释', previous)
    assert invalid[3] == previous
    assert invalid[1] == ''


def test_export_preserves_request_and_backend(tmp_path, monkeypatch):
    monkeypatch.setattr("app.get_upload_folder", lambda: str(tmp_path))
    result = Analyzer(Settings(backend='mock')).analyze(request())
    markdown, structured = export_result(result.model_dump_json())
    assert json.loads(Path(structured).read_text()) == result.model_dump(mode='json')
    text = Path(markdown).read_text()
    assert '原始命令' in text and '模拟模式' in text and 'Get-ChildItem' in text


def test_auth_requires_pair_and_secrets_are_not_in_repr():
    assert launch_auth(Settings()) is None
    with pytest.raises(ConfigurationError):
        launch_auth(Settings(app_username='student'))
    settings = Settings(app_username='student', app_password='private-password')
    assert launch_auth(settings) == ('student', 'private-password')
    assert 'private-password' not in repr(settings)


def test_local_backend_is_lazy_and_failure_keeps_static_findings(monkeypatch):
    settings = Settings(backend='local')
    client = create_client(settings)
    assert client.backend == 'local' and client.model is None
    monkeypatch.setitem(sys.modules, 'torch', ModuleType('torch'))
    def fail():
        raise RuntimeError('private-weight-path')
    monkeypatch.setattr(client, '_load', fail)
    dangerous = request().model_copy(update={'command': 'rm -rf /'})
    result = Analyzer(settings, client=client).analyze(dangerous)
    assert result.backend == 'local' and result.model is None
    assert result.overall_risk.value == 'critical'
    assert 'private-weight-path' not in result.model_dump_json()


def rows():
    result = Analyzer(Settings(backend='mock')).analyze(request())
    answer = result.model.model_dump(mode='json')
    row = {'request': request().model_dump(mode='json'), 'expected': answer, 'parsed': answer}
    return [row, {**row, 'parsed': None}]


def test_invalid_conversion_counts_as_failure_in_denominator():
    metrics = summarize(rows())
    assert metrics['conversion_total'] == 2
    assert metrics['conversion_exact_match'] == 0.5
    assert metrics['valid_json_rate'] == metrics['risk_accuracy'] == 0.5


def test_comparison_recomputes_scores_and_rejects_different_sets():
    base = {'model': 'same-model', 'adapter': None, 'records': rows(), 'conversion_exact_match': 1.0}
    tuned = {**base, 'adapter': 'adapter-dir'}
    assert '50.00%' in compare(base, tuned)
    with pytest.raises(ValueError, match='相同顺序'):
        compare(base, {**tuned, 'records': rows()[:1]})
    with pytest.raises(ValueError, match='基础模型必须相同'):
        compare(base, {**tuned, 'model': 'other-model'})
