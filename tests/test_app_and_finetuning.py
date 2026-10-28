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


def test_launch_auth_stays_open_when_nothing_configured(tmp_path):
    import app
    settings = Settings(users_db_path=str(tmp_path / "users.json"))
    auth, store = app.launch_auth(settings)
    assert auth is None
    assert store.has_any_user() is False


def test_launch_auth_gates_with_admin_credentials_and_registered_users(tmp_path):
    import app
    settings = Settings(users_db_path=str(tmp_path / "users.json"), app_username="student", app_password="correct-horse")
    auth, store = app.launch_auth(settings)
    assert callable(auth)
    assert auth("student", "correct-horse") is True
    assert auth("student", "wrong") is False
    store.register("newkid", "a-long-password")
    assert auth("newkid", "a-long-password") is True


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


def test_precision_excludes_bf16_emulation_on_turing():
    from types import SimpleNamespace
    from src.finetuning import supports_native_bf16
    for major, expected in [(7, False), (8, True)]:
        fake_torch = SimpleNamespace(cuda=SimpleNamespace(
            get_device_capability=lambda index: (major, 5),
            is_bf16_supported=lambda: True,
        ))
        assert supports_native_bf16(fake_torch) is expected
