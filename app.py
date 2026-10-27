"""Gradio entry point. Commands are text only and are never executed."""

import html
import json
import os
import re
import time
from datetime import datetime, timezone

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import gradio as gr
from gradio.processing_utils import save_bytes_to_cache
from gradio.utils import get_upload_folder
from pydantic import ValidationError

from src.analyzer import Analyzer
from src.config import ConfigurationError, Settings, load_settings
from src.examples import gradio_examples
from src.schemas import AnalysisRequest, AnalysisResult, Mode, RISK_LABELS, Shell

EMPTY_REPORT = "输入命令并点击“分析命令”以查看结果。"
CSS = """
.gradio-container { max-width: 1280px !important; }
.shellguard-head { background: linear-gradient(120deg, #0f172a, #164e63); border-radius: 20px; padding: 28px !important; margin-bottom: 18px; }
.shellguard-head h1, .shellguard-head p { color: #f8fafc !important; }
.shellguard-head h1 { font-size: 34px !important; }
#result-panel { border: 1px solid var(--border-color-primary); border-radius: 16px; padding: 22px; min-height: 300px; }
#analysis-summary { padding: 12px; border-radius: 10px; background: var(--background-fill-secondary); }
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
        "local": "本地模型已返回" if result.model else "本地模型推理失败",
        "real": "真实 API 已返回" if result.model else "真实 API 调用失败（未获得有效模型分析）",
        "unconfigured": "API 配置不完整（未调用模型）",
    }[result.backend]
    request = result.request
    header = f"## 总风险：{RISK_LABELS[result.overall_risk]}（{result.overall_risk.value}）\n{backend}"
    context = f"**模式：**{request.mode.value} · {request.source_shell.value}"
    if request.mode == Mode.CONVERT:
        context += f" → {request.target_shell.value}"
    context += f"\n\n### 原始命令\n{_code(request.command)}"
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


def history_choices(history):
    return [(f"{item['time']} · {json.loads(item['payload'])['request']['command'][:48]}", str(index))
            for index, item in enumerate(history)]


def analyze_session(analyzer, raw, source, target, mode, history):
    started = time.perf_counter()
    report, payload, copied = run_analysis(analyzer, raw, source, target, mode)
    history = list(history or [])
    if payload:
        result = AnalysisResult.model_validate_json(payload)
        history.insert(0, {"time": datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
                           "payload": payload, "report": report})
        history = history[:20]
        status = "分析完成" if result.model else "模型未完成 · 静态检测可用"
        summary = f"**{status}** · 风险：{RISK_LABELS[result.overall_risk]} · 命中 {len(result.static_findings)} 条规则 · {time.perf_counter() - started:.2f} 秒"
    else:
        summary = "**请检查输入**"
    return report, payload, copied, history, gr.update(choices=history_choices(history), value=None), summary, gr.update(value=None, interactive=False), gr.update(value=None, interactive=False)


def restore_history(index, history):
    if index is None:
        return (gr.skip(),) * 10
    try:
        item = history[int(index)]
        request = AnalysisResult.model_validate_json(item["payload"]).request
    except (IndexError, ValueError, TypeError):
        return (gr.skip(),) * 10
    return (request.command, request.source_shell.value, request.target_shell.value, request.mode.value,
            item["report"], item["payload"], item["report"], "**已恢复会话记录**", gr.update(value=None, interactive=False), gr.update(value=None, interactive=False))


def export_result(payload):
    if not payload:
        raise gr.Error("请先完成一次分析，再导出结果。")
    result = AnalysisResult.model_validate_json(payload)
    report, structured, _ = _render_result(result)
    cache = get_upload_folder()
    return (
        save_bytes_to_cache(report.encode("utf-8"), "shellguard-analysis.md", cache),
        save_bytes_to_cache(structured.encode("utf-8"), "shellguard-analysis.json", cache),
    )


def launch_auth(settings):
    password = settings.app_password.get_secret_value()
    if bool(settings.app_username) != bool(password):
        raise ConfigurationError("访问口令配置不完整：APP_USERNAME 与 APP_PASSWORD 必须同时填写。")
    return (settings.app_username, password) if password else None


def create_app(settings: Settings | None = None) -> gr.Blocks:
    settings = settings or load_settings()
    analyzer = Analyzer(settings)
    try:
        backend = settings.effective_backend
        configuration_error = None
    except ConfigurationError as exc:
        backend, configuration_error = "unconfigured", str(exc)

    with gr.Blocks(title="ShellGuard AI · Shell 命令分析", theme=gr.themes.Soft(primary_hue="cyan", neutral_hue="slate",
                   font=["system-ui", "sans-serif"], font_mono=["ui-monospace", "monospace"]),
                   css=CSS, analytics_enabled=False, delete_cache=(3600, 3600)) as demo:
        history = gr.State([])
        gr.Markdown("# ShellGuard AI\n跨 Shell 命令智能分析助手\n\n读懂命令 · 迁移语法 · 识别风险", elem_classes=["shellguard-head"])
        if backend == "mock":
            gr.Markdown("**离线演示** · 未调用大模型。12 组预置样例可体验完整流程，未知命令仅提供静态检测。")
        elif backend == "local":
            label = "LoRA 微调模型" if settings.local_adapter else "基础模型"
            gr.Markdown(f"**本地推理 · {label}** · 首次分析需加载权重，CPU 推理可能较慢。")
        elif backend == "real":
            gr.Markdown(f"**在线模型 · {_plain(settings.model_name)}** · 调用状态以每次分析结果为准。")
        else:
            gr.Markdown(f"**配置提示：**{_plain(configuration_error)} 静态检测仍可使用。")
        with gr.Row():
            with gr.Column(scale=5, min_width=320):
                gr.Markdown("### 01 / 输入命令")
                mode = gr.Radio([x.value for x in Mode], value=Mode.EXPLAIN.value, label="分析任务")
                with gr.Row():
                    source = gr.Dropdown([x.value for x in Shell], value=Shell.BASH.value, label="源 Shell")
                    target = gr.Dropdown([x.value for x in Shell], value=Shell.POWERSHELL.value, label="目标 Shell", interactive=False)
                command = gr.Textbox(label="命令文本", placeholder="输入 ls，或从下方示例开始…", lines=7, max_lines=16, max_length=8000)
                with gr.Row():
                    analyze_button = gr.Button("分析命令", variant="primary")
                    clear_button = gr.Button("清空输入与结果")
                gr.Markdown("仅分析文本，不执行命令。请勿输入密码、令牌等敏感内容。")
                with gr.Accordion("示例库 · 点击载入", open=True):
                    gr.Examples(examples=gradio_examples(), inputs=[command, source, target, mode], examples_per_page=6, label="12 个场景")
                with gr.Accordion("本次会话记录", open=False):
                    gr.Markdown("最多保留最近 20 条；不同浏览器会话相互隔离，刷新页面后重置。")
                    history_picker = gr.Dropdown(choices=[], label="选择记录以恢复输入与结果", interactive=True)
                    clear_history = gr.Button("清除会话记录")
            with gr.Column(scale=7, min_width=320):
                gr.Markdown("### 02 / 分析结果")
                summary = gr.Markdown("等待分析 · 选择示例或输入命令开始", elem_id="analysis-summary")
                with gr.Tabs():
                    with gr.Tab("可读分析"):
                        report = gr.Markdown(EMPTY_REPORT, sanitize_html=True, elem_id="result-panel")
                    with gr.Tab("结构化 JSON"):
                        structured = gr.Code(label="JSON", language="json", interactive=False, lines=24)
                    with gr.Tab("复制与导出"):
                        copy_result = gr.Textbox(label="Markdown 文本", interactive=False, lines=12, show_copy_button=True)
                        export_button = gr.Button("生成下载文件")
                        with gr.Row():
                            download_md = gr.DownloadButton("下载 Markdown", value=None, interactive=False)
                            download_json = gr.DownloadButton("下载 JSON", value=None, interactive=False)
        with gr.Accordion("使用指南与实验展示", open=False):
            gr.Markdown("1. **命令解释**：输入 `ls`，查看含义、风险与验证建议。\n2. **跨 Shell 转换**：选择 Bash → PowerShell，输入 `ls`，对照转换结果及语义差异。\n3. **风险分析**：输入 `rm -rf /`，查看严重风险及命中的静态规则（不会执行）。\n4. **保存材料**：在复制与导出页下载分析文件；会话记录可恢复之前的案例。\n\n真实 API、本地基础模型和 LoRA 模型均通过服务端环境变量切换。离线演示不代表真实推理或微调效果。")

        outputs = [report, structured, copy_result]
        analyze_button.click(lambda *values: analyze_session(analyzer, *values),
                             [command, source, target, mode, history],
                             [*outputs, history, history_picker, summary, download_md, download_json],
                             api_name="analyze", concurrency_limit=4)
        mode.change(lambda value: gr.update(interactive=value == Mode.CONVERT.value),
                    inputs=[mode], outputs=[target], queue=False, api_name=False)
        clear_button.click(lambda: ("", EMPTY_REPORT, "", "", "等待分析", gr.update(value=None, interactive=False), gr.update(value=None, interactive=False)),
                           outputs=[command, *outputs, summary, download_md, download_json], api_name=False)
        history_picker.input(restore_history, [history_picker, history],
                             [command, source, target, mode, *outputs, summary, download_md, download_json], api_name=False)
        clear_history.click(lambda: ([], gr.update(choices=[], value=None)), outputs=[history, history_picker], api_name=False)
        export_button.click(lambda payload: tuple(gr.update(value=path, interactive=True) for path in export_result(payload)),
                            [structured], [download_md, download_json], api_name=False)
    return demo.queue(max_size=20, default_concurrency_limit=4)


if __name__ == "__main__":
    config = load_settings()
    auth = launch_auth(config)
    create_app(config).launch(server_name=config.host, server_port=config.port, share=False,
                             auth=auth, show_error=False, max_threads=8)
