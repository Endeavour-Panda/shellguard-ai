"""Conservative text checks; never execute input or probe installed commands."""

import re
import shlex

from src.schemas import Shell

AUTO_SHELL = "自动识别"


def detect_shell(command: str) -> tuple[Shell, str]:
    # Anchor command names to statement boundaries, avoiding quoted arguments.
    ps = bool(re.search(r"(?im)(?:^|[;|\n])\s*(?:&\s*)?(?:[a-z]+-[a-z][\w-]*|\$env:|\$[\w]+\s*=)", command))
    cmd = bool(re.search(r"(?im)(?:^|[&|\n])\s*(?:@?echo\s+off\b|(?:dir|type|copy|del|rmdir|set|setlocal|endlocal)\b)", command)
               or re.search(r"%[A-Za-z_][\w]*%", command))
    bash = bool(re.search(r"(?m)(?:^|[;|&\n])\s*(?:sudo\s+)?(?:ls|pwd|cat|grep|find|rm|chmod|chown|export|source|touch|sed|awk|bash)\b", command)
                or command.startswith("#!/bin/"))
    candidates = [s for s, hit in [(Shell.POWERSHELL, ps), (Shell.CMD, cmd), (Shell.BASH, bash)] if hit]
    if len(candidates) == 1:
        return candidates[0], f"自动识别：{candidates[0].value}（基于命令特征，可手动修改）"
    if len(candidates) > 1:
        return Shell.BASH, "检测到多种 Shell 特征，暂按 Bash 分析；请手动确认源 Shell。"
    return Shell.BASH, "命令可能适用于多种 Shell，暂按 Bash 分析；可手动选择 PowerShell 或 CMD。"


def validate_command_text(command: str) -> None:
    if not command.strip():
        raise ValueError("请输入需要分析的命令")
    if any(ord(c) < 32 and c not in "\n\r\t" for c in command) or "\x7f" in command:
        raise ValueError("命令含有不可见控制字符，请删除后重试")
    if re.fullmatch(r"[\s|&;<>]+", command):
        raise ValueError("输入只有操作符，缺少命令或重定向目标")


def input_feedback(command: str, source: str) -> str:
    try:
        validate_command_text(command)
    except ValueError as exc:
        return f"输入检测：{exc}"
    shell, note = detect_shell(command) if source == AUTO_SHELL else (Shell(source), f"手动选择：{source}")
    if shell == Shell.BASH and "<<" not in command:
        try:
            shlex.split(command, comments=True)
        except ValueError:
            note += "；疑似引号未闭合或转义未完成，请检查。"
    return note + "\n\n仅做文本初检，无法确认命令是否安装或完整语法是否合法；危险命令仍会进入风险分析。"
