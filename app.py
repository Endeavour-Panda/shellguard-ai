"""Gradio entry point. Commands are text only and are never executed."""

import html
import json
import os
import re

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import gradio as gr
from pydantic import ValidationError

from src.analyzer import Analyzer
from src.config import ConfigurationError, Settings, load_settings
from src.examples import gradio_examples
from src.schemas import AnalysisRequest, AnalysisResult, Mode, RISK_LABELS, Shell

EMPTY_REPORT = "输入命令并点击“分析命令”以查看结果。"
CSS = """
.shellguard-head { border-bottom: 1px solid var(--border-color-primary); padding-bottom: 12px; }
.shellguard-head h1 { font-size: 28px; letter-spacing: -0.5px; }
footer { display: none !important; }
"""


def _plain(text: str) -> str:
    """Render untrusted prose literally, including Markdown links and images."""
    escaped = html.escape(text, quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", escaped)


def _code(text: str) -> str:
    fence = "`" * max(3, max((len(x) + 1 for x in re.findall(r"`+", text)), default=3))
    return f"{fence}text\n{text}\n{fence}"


def _render_result(result: AnalysisResult) -> tuple[str, str, str]:
    backend = {
        "mock": "模拟模式（未调用 API）",
        "real": "真实 API 已返回" if result.model else "真实 API 调用失败（未获得有效模型分析）",
        "unconfigured": "API 配置不完整（未调用模型）",
    }[result.backend]
    request = result.request
    header = f"## 总风险：{RISK_LABELS[result.overall_risk]}（{result.overall_risk.value}）\n{backend}"
    context = f"**模式：**{request.mode.value} · {request.source_shell.value} → {request.target_shell.value}"
    if result.model is None:
        model_section = f"### 模型分析未完成\n{_plain(result.error or '没有有效结果。')}\n\n静态风险检测仍独立运行。"
    else:
        analysis = result.model
        model_section = f"### 命令解释\n{_plain(analysis.explanation)}"
        if request.mode == Mode.CONVERT:
            if analysis.converted_command is not None:
                command_section = _code(analysis.converted_command)
            elif len([line for line in request.command.splitlines() if line.strip()]) > 1:
                command_section = "整段包含多条命令，其中至少一条无法安全等价转换，因此未生成可执行命令。请逐条提交以分别查看可转换项和被拒绝项。"
            else:
                command_section = "未生成转换命令，不能确认等价转换。"
            source_note = {
                "rule": "确定性内置规则",
                "model": "模型生成",
                "none": "未生成",
            }[result.conversion_source]
            model_section += f"\n\n### 转换结果（{source_note}，未经执行验证）\n{command_section}"
        label = "模拟风险占位值（无模型判断）" if result.backend == "mock" else "模型风险判断"
        reasons = "\n".join(f"- {_plain(x)}" for x in analysis.risk_reasons) or "- 无附加说明。"
        differences = "\n".join(f"- {_plain(x)}" for x in analysis.semantic_differences) or "- 未提供差异；仍需检查 Shell 版本、路径和编码。"
        suggestions = "\n".join(f"- {_plain(x)}" for x in analysis.validation_suggestions)
        model_section += f"\n\n### {label}\n{RISK_LABELS[analysis.risk_level]}（{analysis.risk_level.value}）\n\n{reasons}\n\n### 语义差异\n{differences}\n\n### 验证建议\n{suggestions}"
    def finding_location(finding):
        source = "原始命令" if finding.origin == "input" else "转换命令"
        return f"{source}第 {finding.statement_index} 条" if finding.statement_index else source

    rows = "\n".join(
        f"- **{RISK_LABELS[x.level]} · {finding_location(x)} · {x.code}**：{_plain(x.reason)} 建议：{_plain(x.suggestion)}"
        for x in result.static_findings
    ) or "- 文本启发式扫描未命中规则，不代表命令安全。"
    rendered = f"{header}\n\n{context}\n\n{model_section}\n\n### 静态规则检测（独立于模型）\n{rows}\n\n> **安全提示：** {_plain(result.warning)}"
    payload = json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2)
    return rendered, payload, rendered


def run_analysis(analyzer: Analyzer, raw: str, source: str, target: str, mode: str) -> tuple[str, str, str]:
    try:
        request = AnalysisRequest(command=raw, source_shell=source, target_shell=target, mode=mode)
    except ValidationError as exc:
        details = "；".join(e["msg"] for e in exc.errors(include_input=False, include_url=False))
        return f"### 输入错误\n{_plain(details)}", "", ""
    return _render_result(analyzer.analyze(request))


def create_app(settings: Settings | None = None) -> gr.Blocks:
    settings = settings or load_settings()
    analyzer = Analyzer(settings)
    try:
        backend = settings.effective_backend
        configuration_error = None
    except ConfigurationError as exc:
        backend, configuration_error = "unconfigured", str(exc)

    with gr.Blocks(title="ShellGuard AI · Shell 命令分析", theme=gr.themes.Default(), css=CSS, analytics_enabled=False) as demo:
        gr.Markdown("# ShellGuard AI\n跨 Shell 命令智能分析助手 · 文本分析，不执行命令", elem_classes=["shellguard-head"])
        if backend == "mock":
            gr.Markdown("**离线模拟模式 · 未调用模型 API。** 12 组示例使用预置对照；未知命令仅提供静态检测，不虚构模型分析。")
        elif backend == "real":
            gr.Markdown(f"**真实 API 模式 · 模型：{_plain(settings.model_name)}。** 调用成功与否以每次结果为准。请勿提交凭据或敏感内容。")
        else:
            gr.Markdown(f"**配置提示：**{_plain(configuration_error)} 静态检测仍可使用。")
        with gr.Row():
            mode = gr.Dropdown([x.value for x in Mode], value=Mode.EXPLAIN.value, label="功能模式", interactive=True)
            source = gr.Dropdown([x.value for x in Shell], value=Shell.BASH.value, label="源 Shell", interactive=True)
            target = gr.Dropdown([x.value for x in Shell], value=Shell.POWERSHELL.value, label="目标 Shell（转换模式使用）", interactive=False)
        command = gr.Textbox(label="待分析命令", placeholder="例如：ls 或 Get-ChildItem", lines=5, max_lines=14, max_length=8000)
        with gr.Row():
            analyze_button = gr.Button("分析命令", variant="primary")
            clear_button = gr.Button("清空输入与结果")
        with gr.Accordion("12 个可载入示例", open=False):
            gr.Markdown("点击载入命令及 Shell。涉及文件的示例需预先准备测试文件；删除示例存在数据丢失风险。")
            gr.Examples(examples=gradio_examples(), inputs=[command, source, target, mode], examples_per_page=12, label="示例命令")
        report = gr.Markdown(EMPTY_REPORT, sanitize_html=True)
        with gr.Accordion("复制完整分析结果", open=False):
            copy_result = gr.Textbox(label="分析结果（Markdown 文本）", interactive=False, lines=10, show_copy_button=True)
        with gr.Accordion("结构化 JSON", open=False):
            structured = gr.Code(label="JSON（右上角可复制）", language="json", interactive=False, lines=20)
        with gr.Accordion("页面使用说明", open=False):
            gr.Markdown("1. 选择功能模式和源 Shell；转换时再选择目标 Shell。\n2. 输入命令或点击示例，然后点击“分析命令”。\n3. 分别查看模型判断与静态检测，并核对原始/转换命令的风险来源。\n4. 在复制区点击复制按钮；清空按钮同时清空输入和结果。\n\n本应用不执行命令；低风险、模拟对照或模型输出均不构成安全保证。")

        outputs = [report, structured, copy_result]
        analyze_button.click(lambda *values: run_analysis(analyzer, *values), [command, source, target, mode], outputs, api_name="analyze", concurrency_limit=4)
        mode.change(
            lambda value: (gr.update(interactive=value == Mode.CONVERT.value), EMPTY_REPORT, "", ""),
            inputs=[mode], outputs=[target, *outputs], queue=False, api_name=False,
        )
        clear_button.click(lambda: ("", EMPTY_REPORT, "", ""), outputs=[command, *outputs], queue=False, api_name=False)
    return demo.queue(max_size=20, default_concurrency_limit=4)


if __name__ == "__main__":
    config = load_settings()
    create_app(config).launch(server_name=config.host, server_port=config.port, share=False, show_error=False, max_threads=8)
