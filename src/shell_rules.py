"""Conservative lexical heuristics, NOT a shell parser or a safety verifier.

Patterns can also match comments/quoted text; indirect aliases and obfuscation can
escape detection. Findings are warnings, never an execution authorization.
"""

import re

from src.schemas import RiskLevel, RuleFinding, Shell


DELETE_PATTERN = re.compile(r"(?i)(?<![\w-])(?:rm|rmdir|rd|del|erase|remove-item|ri)(?![\w-])")
BROAD_TARGET_PATTERN = re.compile(
    r"(?ix)(?<!\S)[\"']?(?:/|/(?:home|etc|usr|var|tmp)/?|[a-z]:[\\/]|~/?|"
    r"\$(?:HOME|\{HOME\}|env:USERPROFILE)|%USERPROFILE%)[\"']?(?!\S)"
)


def _command_segments(command: str) -> list[str]:
    """Split control operators outside simple quotes for local risk scoping."""
    segments: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    for char in command:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\" and quote != "'":
            current.append(char)
            escaped = True
            continue
        if char in {'"', "'"}:
            quote = None if quote == char else char if quote is None else quote
            current.append(char)
            continue
        if quote is None and char in {"\r", "\n", ";", "|", "&"}:
            segment = "".join(current).strip()
            if segment:
                segments.append(segment)
            current = []
            continue
        current.append(char)
    segment = "".join(current).strip()
    if segment:
        segments.append(segment)
    return segments


def detect_risks(
    command: str, shell: Shell, *, origin: str = "input", statement_index: int | None = None
) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    def add(code: str, level: RiskLevel, reason: str, suggestion: str) -> None:
        findings.append(RuleFinding(
            code=code, level=level, reason=reason, suggestion=suggestion,
            origin=origin, statement_index=statement_index,
        ))

    # Include common aliases and cmdlets regardless of the selected Shell: the
    # selection may itself be wrong, and PowerShell aliases vary by platform.
    delete_segments = [segment for segment in _command_segments(command) if DELETE_PATTERN.search(segment)]
    deleting = bool(delete_segments)
    destructive = bool(re.search(r"(?i)(?<![\w-])(?:format(?:\.com)?|mkfs(?:\.\w+)?|diskpart|dd)(?![\w-])", command))
    if deleting:
        add("deletion", RiskLevel.HIGH, "检测到删除命令或别名，可能造成不可恢复的数据丢失。", "先列出精确目标并备份；PowerShell 可先检查 -WhatIf 的适用性。")
    if destructive:
        add("disk_write", RiskLevel.CRITICAL, "可能涉及磁盘格式化、分区管理或原始设备写入。", "停止直接尝试，逐项确认设备和备份，在隔离环境审查。")
    broad_delete = any(BROAD_TARGET_PATTERN.search(segment) or "*" in segment or "?" in segment for segment in delete_segments)
    if broad_delete:
        add("broad_delete", RiskLevel.CRITICAL, "删除目标包含根目录、家目录或通配符，实际范围可能很大。", "展开变量并人工核对绝对路径和匹配清单，勿对广泛目录直接操作。")
    if re.search(r"(?i)(?:>>?|\b(?:out-file|set-content|add-content|tee-object|copy-item|move-item|cp|mv|copy|move)\b)", command):
        add("overwrite", RiskLevel.MEDIUM, "检测到重定向、写文件、复制或移动操作，可能覆盖或追加目标内容。", "确认源与目标，备份现有文件；区分 > 覆盖与 >> 追加。")
    remote = bool(re.search(r"(?i)\b(?:curl|wget|invoke-webrequest|invoke-restmethod|iwr|irm|downloadstring)\b", command))
    evaluator = bool(re.search(r"(?i)\b(?:bash|sh|zsh|iex|invoke-expression|powershell|pwsh|cmd)\b", command))
    if remote and evaluator and re.search(r"[|;\r\n]|&&|\$\(|`", command):
        add("remote_execution", RiskLevel.CRITICAL, "下载内容可能直接交给解释器执行，内容和来源无法静态验证。", "先保存为文件、核验来源及完整内容，避免下载后直接执行。")
    if re.search(r"(?i)(?<![\w-])(?:eval|iex|invoke-expression)(?![\w-])|\b(?:bash|sh|cmd|powershell|pwsh)\s+(?:-[cC]|/[cC]|-Command)\b", command):
        add("dynamic_execution", RiskLevel.HIGH, "检测到动态求值或嵌套解释器，字符串可能被再次解析。", "逐层检查字符串来源、引号和变量；不要对不可信文本求值。")
    if re.search(r"[|;&]|\r|\n", command):
        add("composition", RiskLevel.MEDIUM, "存在管道、连接符或多行命令；各 Shell 的数据类型与失败处理不同。", "逐段核对文本/对象管道、退出码、短路逻辑和换行续行规则。")
    if re.search(r"\$[A-Za-z_{(]|%[^%\r\n]+%|![A-Za-z_][^!\r\n]*!", command):
        add("variable_expansion", RiskLevel.MEDIUM, "存在变量或命令替换；空值、空格、通配符和展开时机可能改变含义。", "确认所有变量的实际值；分别核对 Bash、PowerShell、CMD 的展开规则。")
    if re.search(r"\$\([^)]|`[^`]+`", command):
        add("substitution", RiskLevel.HIGH, "可能包含命令替换或反引号；解析过程中可能运行子命令。", "人工确认每个替换表达式；注意 PowerShell 的反引号通常是转义符。")
    if any(char in command for char in ('"', "'", "`", "^", "\\")):
        add("quoting_escaping", RiskLevel.MEDIUM, "存在引号或转义字符，其语义随 Shell 和上下文变化。", "CMD 单引号不负责分组；PowerShell 与 Bash 的反引号含义不同，检查嵌套引号。")
    if re.search(r"(?i)(?:[a-z]:[\\/]|\\\\|(?:^|\s)\.{1,2}[/\\]|~[/\\]|/mnt/|\$(?:HOME|env:USERPROFILE)(?:[/\\]|\b)|%USERPROFILE%(?:[/\\]|\b)|[?*])", command):
        add("path_semantics", RiskLevel.MEDIUM, "检测到相对路径、平台路径或通配符，目标依赖当前目录及运行平台。", "确认目标操作系统、工作目录、盘符和路径大小写；使用专用测试目录。")
    if re.search(r"(?i)\b(?:sudo|su|runas|chmod|chown|set-executionpolicy|icacls)\b", command):
        add("privileges", RiskLevel.HIGH, "命令可能提升权限或修改访问控制/执行策略。", "确认最小权限需求和影响范围，审查权限变更。")
    if shell == Shell.CMD and re.search(r"(?i)\b(?:for|setlocal|enabledelayedexpansion)\b", command):
        add("cmd_expansion", RiskLevel.MEDIUM, "CMD 循环或延迟展开存在交互命令行与批处理文件语法差异。", "确认在交互 CMD 还是 .bat 中使用；核对 % 与 %% 和 !var!。")
    return findings


def detect_risks_by_statement(command: str, shell: Shell, *, origin: str = "input") -> list[RuleFinding]:
    """Label multiline findings while retaining rules that span multiple lines."""
    statements = [(index, line) for index, line in enumerate(command.splitlines(), start=1) if line.strip()]
    if len(statements) <= 1:
        return detect_risks(command, shell, origin=origin)

    findings = [
        finding
        for index, statement in statements
        for finding in detect_risks(statement, shell, origin=origin, statement_index=index)
    ]
    existing_codes = {finding.code for finding in findings}
    for finding in detect_risks(command, shell, origin=origin):
        if finding.code not in existing_codes:
            findings.append(finding)
    return findings
