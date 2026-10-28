"""Gradio entry point. Commands are text only and are never executed."""

import html
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import gradio as gr
from gradio.processing_utils import save_bytes_to_cache
from gradio.utils import get_upload_folder
from pydantic import ValidationError

from src.analyzer import Analyzer
from src.config import ConfigurationError, Settings, load_settings
from src.examples import gradio_examples
from src.schemas import AnalysisRequest, AnalysisResult, Mode, RISK_LABELS, RiskLevel, Shell

EMPTY_REPORT = "## 从一条命令开始\n\n选择左侧任务，输入命令或载入示例，然后点击 **分析命令**。\n\n---\n\n**读懂命令** · 理解参数与执行意图\n\n**转换语法** · 在三种 Shell 之间迁移常见用法\n\n**识别风险** · 核对删除、覆盖及远程执行等操作\n\n> 结果将在这里呈现。所有命令仅作文本分析，不会执行。"
CSS = """
.gradio-container { max-width: 1320px !important; padding: 28px 24px !important; }
body { background: #f3f6fa; }
.sg-hero { display: grid; grid-template-columns: 1.35fr 1fr; gap: 36px; align-items: center; padding: 36px 40px; border-radius: 24px; color: #edf6ff; background: radial-gradient(ellipse at 85% 15%, #16556a 0, transparent 56%), #101d35; box-shadow: 0 16px 48px #10213a14; }
.sg-eyebrow { color: #8ee1d5; font-size: 12px; font-weight: 600; letter-spacing: 2px; margin-bottom: 14px; }
.sg-hero h1 { font-size: clamp(30px, 4vw, 44px); line-height: 1.12; letter-spacing: -1.5px; margin: 0 0 12px; color: #fff; font-weight: 750; }
.sg-hero .sg-subtitle { color: #c4d5e8; font-size: 16px; line-height: 1.8; margin: 0; }
.sg-tags { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 22px; }
.sg-tags span { padding: 6px 12px; border: 1px solid #ffffff24; border-radius: 999px; font-size: 12px; color: #d9eaf5; background: #ffffff08; }
.sg-terminal { padding: 20px 22px; border: 1px solid #ffffff24; border-radius: 16px; background: #071327a6; box-shadow: 0 16px 28px #00000014; }
.sg-terminal-top { display: flex; align-items: center; gap: 6px; color: #a3b9ce; font-size: 11px; margin-bottom: 22px; }
.sg-dot { width: 7px; height: 7px; border-radius: 50%; background: #476079; }
.sg-terminal-top .sg-terminal-label { margin-left: auto; letter-spacing: 1px; }
.sg-terminal code { color: #e5f4ff; font-size: 15px; line-height: 1.8; }
.sg-terminal .sg-prompt { color: #60d7be; margin-right: 12px; }
.sg-terminal .sg-arrow { color: #8299b2; font-size: 12px; margin: 12px 0; padding-left: 24px; }
.sg-terminal-note { color: #94adc5; border-top: 1px solid #ffffff14; padding-top: 14px; margin-top: 18px; font-size: 11px; }
#input-panel, #output-panel { border: 1px solid var(--border-color-primary); border-radius: 20px; padding: 22px; background: var(--background-fill-primary); box-shadow: 0 5px 18px #10213a04; }
#workspace { gap: 20px; margin-top: 8px; }
#input-panel h3, #output-panel h3 { font-size: 18px; letter-spacing: -.3px; }
#input-panel textarea { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; line-height: 1.8; }
#analyze-button { background: #087f8c; color: white; border: 1px solid #087f8c; border-radius: 11px; min-height: 46px; font-weight: 650; box-shadow: 0 4px 12px #087f8c20; }
#analyze-button:hover { background: #066a75; border-color: #066a75; }
#analysis-summary { padding: 12px 14px; border: 1px solid var(--border-color-primary); border-radius: 11px; background: var(--background-fill-secondary); font-size: 13px; }
#result-panel { padding: 18px 8px; min-height: 350px; }
#result-panel h2 { font-size: 22px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
#result-panel h3 { margin-top: 28px; margin-bottom: 10px; font-size: 12px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #0b6e63; padding-bottom: 7px; border-bottom: 1px solid var(--border-color-primary); }
#result-panel pre { border-radius: 10px; }
#result-panel blockquote { border-left: 3px solid #16a6a0; padding: 10px 14px; }
.dark #result-panel h3 { color: #6fe3bd; }
.sg-badge { display: inline-flex; align-items: center; gap: 6px; padding: 3px 11px; border-radius: 999px; font-size: 12px; font-weight: 700; letter-spacing: .2px; white-space: nowrap; vertical-align: middle; }
.sg-badge::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; flex: 0 0 auto; }
.sg-badge-lg { font-size: 14px; padding: 5px 14px; }
.sg-badge-low { background: #e3f6f1; color: #0b7a5c; }
.sg-badge-medium { background: #fef2d4; color: #92650a; }
.sg-badge-high { background: #ffe3cf; color: #9a3b12; }
.sg-badge-critical { background: #fde1e1; color: #b42318; }
.dark .sg-badge-low { background: #0b7a5c26; color: #6fe3bd; }
.dark .sg-badge-medium { background: #92650a26; color: #f6c768; }
.dark .sg-badge-high { background: #9a3b1226; color: #ffb088; }
.dark .sg-badge-critical { background: #b4231826; color: #ff9d9d; }
.sg-status { display: flex; align-items: center; gap: 10px; padding: 11px 16px; border-radius: 12px; font-size: 13px; line-height: 1.6; border: 1px solid transparent; margin: 4px 0 6px; }
.sg-status::before { content: ""; width: 8px; height: 8px; border-radius: 50%; flex: 0 0 auto; }
.sg-status strong { font-weight: 650; }
.sg-status-mock { background: #fef6e0; color: #8a5a00; border-color: #f3dfa0; }
.sg-status-mock::before { background: #d9a512; }
.sg-status-success { background: #e3f6f1; color: #0b6e63; border-color: #b9e8dd; }
.sg-status-success::before { background: #0f9d6b; }
.sg-status-warning { background: #fdecec; color: #9c2626; border-color: #f6c6c6; }
.sg-status-warning::before { background: #d33636; }
.dark .sg-status-mock { background: #8a5a0022; color: #f3c666; border-color: #8a5a0055; }
.dark .sg-status-success { background: #0f9d6b22; color: #6fe3bd; border-color: #0f9d6b55; }
.dark .sg-status-warning { background: #d3363622; color: #ff9d9d; border-color: #d3363655; }
.sg-footer { display: flex; justify-content: space-between; gap: 16px; padding: 22px 4px 4px; color: #708197; font-size: 12px; border-top: 1px solid var(--border-color-primary); margin-top: 8px; }
.sg-footer strong { color: #36516c; font-weight: 600; }
.dark body { background: #0b1220; }
.dark .sg-footer strong { color: #c2d4e5; }
footer { display: none !important; }
@media (max-width: 760px) {
 .gradio-container { padding: 14px 12px !important; }
 .sg-hero { grid-template-columns: 1fr; gap: 22px; padding: 26px 22px; border-radius: 18px; }
 .sg-terminal { padding: 16px 18px; }
 .sg-terminal-top { margin-bottom: 12px; }
 #workspace { flex-direction: column !important; }
 #input-panel, #output-panel { min-width: 0 !important; width: 100% !important; flex: none !important; box-sizing: border-box; padding: 16px; }
 .sg-footer { flex-direction: column; gap: 6px; }
}
"""

HERO_HTML = """
<section class="sg-hero" aria-label="ShellGuard AI 项目介绍">
  <div>
    <div class="sg-eyebrow">燕山大学 · 大模型应用实验</div>
    <h1>ShellGuard AI<span style="color:#62dbc7">.</span></h1>
    <p class="sg-subtitle">让命令更易读，让跨平台转换更清晰。<br>解释命令、迁移语法，先看懂风险再行动。</p>
    <div class="sg-tags"><span>李振昊创作</span><span>Bash / PowerShell / CMD</span><span>仅分析 · 不执行</span></div>
  </div>
  <div class="sg-terminal" aria-label="转换示例：ls 转为 Get-ChildItem">
    <div class="sg-terminal-top"><span class="sg-dot"></span><span class="sg-dot"></span><span class="sg-dot"></span><span class="sg-terminal-label">COMMAND PREVIEW</span></div>
    <div><code><span class="sg-prompt">$</span>ls</code></div>
    <div class="sg-arrow">Bash → PowerShell · 转换示例</div>
    <div><code><span class="sg-prompt">›</span>Get-ChildItem</code></div>
    <div class="sg-terminal-note">理解意图 / 保留参数 / 提示差异</div>
  </div>
</section>
"""

AUTH_MESSAGE = """<div style="text-align:center;padding:12px 0 22px">
<div style="color:#087f8c;font-size:12px;letter-spacing:2px;margin-bottom:12px">燕山大学 · 大模型应用实验</div>
<h1 style="font-size:30px;margin:0 0 12px;letter-spacing:-1px">ShellGuard AI</h1>
<p style="opacity:.75;line-height:1.8">跨 Shell 命令智能分析助手<br>登录后开始解释、转换与风险分析</p>
<div style="font-size:13px;color:#087f8c;margin-top:18px">李振昊创作 · 燕山大学</div></div>"""



def _plain(text: str) -> str:
    """Render untrusted prose literally, including Markdown links and images."""
    escaped = html.escape(text, quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", escaped)


def _code(text: str) -> str:
    fence = "`" * max(3, max((len(x) + 1 for x in re.findall(r"`+", text)), default=3))
    return f"{fence}text\n{text}\n{fence}"


RISK_BADGE_CLASS = {
    RiskLevel.LOW: "sg-badge-low",
    RiskLevel.MEDIUM: "sg-badge-medium",
    RiskLevel.HIGH: "sg-badge-high",
    RiskLevel.CRITICAL: "sg-badge-critical",
}


def _badge(level: RiskLevel, *, large: bool = False) -> str:
    """Colored risk pill. Safe to embed raw in Markdown: level is a closed enum, never model text."""
    classes = f"sg-badge {RISK_BADGE_CLASS[level]}" + (" sg-badge-lg" if large else "")
    return f'<span class="{classes}">{RISK_LABELS[level]} · {level.value}</span>'


def _status_banner(kind: str, html_body: str) -> str:
    return f'<div class="sg-status sg-status-{kind}">{html_body}</div>'


def _render_result(result: AnalysisResult) -> tuple[str, str, str]:
    backend = {
        "mock": "模拟模式（未调用 API）",
        "local": "本地模型已返回" if result.model else "本地模型推理失败",
        "real": "真实 API 已返回" if result.model else "真实 API 调用失败（未获得有效模型分析）",
        "unconfigured": "API 配置不完整（未调用模型）",
    }[result.backend]
    request = result.request
    header = f"## 总风险：{_badge(result.overall_risk, large=True)}\n{backend}"
    context = f"**模式：** {request.mode.value} · {request.source_shell.value}"
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
        model_section += f"\n\n### {label}\n{_badge(analysis.risk_level)}\n\n{reasons}\n\n### 语义差异\n{differences}\n\n### 验证建议\n{suggestions}"
    def finding_location(finding):
        source = "原始命令" if finding.origin == "input" else "转换命令"
        return f"{source}第 {finding.statement_index} 条" if finding.statement_index else source

    rows = "\n".join(
        f"- {_badge(x.level)} **{finding_location(x)} · {x.code}**：{_plain(x.reason)} 建议：{_plain(x.suggestion)}"
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
        summary = f"**{status}** · 风险：{_badge(result.overall_risk)} · 命中 {len(result.static_findings)} 条规则 · {time.perf_counter() - started:.2f} 秒"
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

    with gr.Blocks(title="ShellGuard AI · 李振昊 · 燕山大学", theme=gr.themes.Soft(primary_hue="teal", neutral_hue="slate",
                   font=["system-ui", "sans-serif"], font_mono=["ui-monospace", "monospace"]),
                   css=CSS, analytics_enabled=False, delete_cache=(3600, 3600)) as demo:
        history = gr.State([])
        gr.HTML(HERO_HTML)
        if backend == "mock":
            gr.HTML(_status_banner("mock", "<strong>离线演示</strong> · 未调用大模型。12 组预置样例可体验完整流程，未知命令仅提供静态检测。"))
        elif backend == "local":
            label = "LoRA 微调模型" if settings.local_adapter else "基础模型"
            model_file = html.escape(Path(settings.local_model).name)
            gr.HTML(_status_banner("success", f"<strong>本地推理 · {label}</strong> · {model_file} · 首次分析需加载权重。"))
        elif backend == "real":
            model_name = html.escape(settings.model_name)
            gr.HTML(_status_banner("success", f"<strong>在线模型 · {model_name}</strong> · 调用状态以每次分析结果为准。"))
        else:
            error_text = html.escape(configuration_error)
            gr.HTML(_status_banner("warning", f"<strong>配置提示：</strong>{error_text} 静态检测仍可使用。"))
        with gr.Row(elem_id="workspace"):
            with gr.Column(scale=5, min_width=320, elem_id="input-panel"):
                gr.Markdown("### 01 / 输入命令")
                mode = gr.Radio([x.value for x in Mode], value=Mode.EXPLAIN.value, label="分析任务")
                with gr.Row():
                    source = gr.Dropdown([x.value for x in Shell], value=Shell.BASH.value, label="源 Shell")
                    target = gr.Dropdown([x.value for x in Shell], value=Shell.POWERSHELL.value, label="目标 Shell", interactive=False)
                command = gr.Textbox(label="命令文本", placeholder="输入 ls，或从下方示例开始…", lines=7, max_lines=16, max_length=8000)
                with gr.Row():
                    analyze_button = gr.Button("分析命令", variant="primary", elem_id="analyze-button")
                    clear_button = gr.Button("清空输入与结果")
                gr.Markdown("仅分析文本，不执行命令。请勿输入密码、令牌等敏感内容。")
                with gr.Accordion("示例库 · 点击载入", open=True):
                    gr.Examples(examples=gradio_examples(), inputs=[command, source, target, mode], examples_per_page=6, label="12 个场景")
                with gr.Accordion("本次会话记录", open=False):
                    gr.Markdown("最多保留最近 20 条；不同浏览器会话相互隔离，刷新页面后重置。")
                    history_picker = gr.Dropdown(choices=[], label="选择记录以恢复输入与结果", interactive=True)
                    clear_history = gr.Button("清除会话记录")
            with gr.Column(scale=7, min_width=320, elem_id="output-panel"):
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

        gr.HTML('<div class="sg-footer"><span><strong>ShellGuard AI</strong> · 让命令更清晰</span><span>李振昊创作 · 燕山大学 · 课程实验作品</span></div>')

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
    create_app(config).launch(server_name=config.host, server_port=config.port, share=config.share,
                             auth=auth, auth_message=AUTH_MESSAGE, show_error=False, max_threads=8)
