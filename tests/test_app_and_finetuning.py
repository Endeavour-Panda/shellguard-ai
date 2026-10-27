from src.config import Settings
from src.examples import EXAMPLES, gradio_examples
from src.finetuning import LoRAOptions, build_training_messages
from src.schemas import AnalysisRequest, ModelAnalysis, Mode, Shell


def test_app_builds_with_offline_settings():
    import app
    demo = app.create_app(Settings())
    assert demo is not None
    assert len(EXAMPLES) >= 10
    assert len(gradio_examples()) >= 10


def test_render_escapes_untrusted_model_markup_and_preserves_copy_payload():
    import app
    from src.analyzer import Analyzer

    request = AnalysisRequest(command="echo x", source_shell=Shell.BASH, target_shell=Shell.CMD, mode=Mode.EXPLAIN)
    result = Analyzer(Settings()).analyze(request)
    result.model = result.model.model_copy(update={"explanation": "![leak](https://invalid.example) <img src=x>"})
    rendered, structured, copied = app._render_result(result)
    assert "![leak]" not in rendered
    assert "\\!\\[leak\\]" in rendered
    assert "&lt;img" in rendered
    assert copied == rendered
    assert '"backend": "mock"' in structured


def test_mode_conversion_example_has_explicitly_unverified_output():
    import app
    from src.analyzer import Analyzer

    request = AnalysisRequest(command="ls", source_shell=Shell.BASH, target_shell=Shell.POWERSHELL, mode=Mode.CONVERT)
    rendered, _, _ = app._render_result(Analyzer(Settings()).analyze(request))
    assert "Get-ChildItem" in rendered
    assert "未经执行验证" in rendered
    assert "静态规则检测" in rendered


def test_lora_preparation_formats_reviewed_answer_without_training():
    request = AnalysisRequest(command="ls", source_shell=Shell.BASH, target_shell=Shell.CMD, mode=Mode.EXPLAIN)
    answer = ModelAnalysis(explanation="列表目录", converted_command=None, risk_level="low", risk_reasons=[],
                           semantic_differences=[], validation_suggestions=["隔离测试"])
    messages = build_training_messages(request, answer)
    assert [item["role"] for item in messages] == ["system", "user", "assistant"]
    assert LoRAOptions().target_modules == ("q_proj", "v_proj")
