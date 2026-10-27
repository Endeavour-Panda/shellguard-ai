"""Small hand-written demo fixtures, not a general translation engine."""

from dataclasses import dataclass

from src.schemas import Mode, Shell


@dataclass(frozen=True)
class Example:
    title: str
    bash: str
    powershell: str
    cmd: str
    explanation: str
    difference: str

    def command_for(self, shell: Shell) -> str:
        return {Shell.BASH: self.bash, Shell.POWERSHELL: self.powershell, Shell.CMD: self.cmd}[shell]


EXAMPLES = (
    Example("列出当前目录", "ls", "Get-ChildItem", "dir", "列出当前目录中的项目。", "隐藏项、输出格式和排序不完全一致；PowerShell 输出对象。"),
    Example("显示当前目录", "pwd", "Get-Location", "cd", "显示当前工作目录。", "PowerShell 返回路径对象；CMD 的 cd 在无参数时显示当前目录。"),
    Example("输出固定文本", "echo hello", "Write-Output hello", "echo hello", "输出固定文本 hello。", "换行和输出编码由 Shell、终端及版本决定。"),
    Example("查看文本文件", "cat notes.txt", "Get-Content -LiteralPath notes.txt", "type notes.txt", "读取 notes.txt 并输出其内容。", "编码、换行与对象/字节流存在差异；需先准备 notes.txt。"),
    Example("创建子目录", "mkdir demo_dir", "New-Item -ItemType Directory -Path demo_dir", "mkdir demo_dir", "在当前目录创建 demo_dir。", "目录已存在时的提示、错误行为和输出不同。"),
    Example("复制文件", "cp notes.txt notes_backup.txt", "Copy-Item -LiteralPath notes.txt -Destination notes_backup.txt", "copy notes.txt notes_backup.txt", "将 notes.txt 复制到 notes_backup.txt，可能覆盖目标。", "覆盖提示、文件元数据及复制模式不完全等价。"),
    Example("移动文件", "mv notes.txt archived_notes.txt", "Move-Item -LiteralPath notes.txt -Destination archived_notes.txt", "move notes.txt archived_notes.txt", "将 notes.txt 移动或重命名为 archived_notes.txt。", "目标存在或跨文件系统时的行为不同。"),
    Example("搜索固定字符串", "grep -F error app.log", "Select-String -SimpleMatch -CaseSensitive -Pattern error -LiteralPath app.log", 'findstr /L /C:"error" app.log', "查找 app.log 中包含大小写敏感固定字符串 error 的行。", "编码支持、输出附加信息和长行处理不同；PowerShell 输出 MatchInfo 对象。"),
    Example("读取 PATH", 'printf "%s\\n" "$PATH"', "$env:PATH", "echo %PATH%", "显示当前进程的 PATH 环境变量。", "Windows 和类 Unix 的路径分隔符与变量展开语法不同。"),
    Example("覆盖写入文本", "echo hello > greeting.txt", "Write-Output hello > greeting.txt", "echo hello > greeting.txt", "将 hello 写入 greeting.txt；已有内容可能被覆盖。", "输出编码、BOM、行尾和 CMD 重定向前空格可能导致文件字节不同。"),
    Example("追加文本", "echo hello >> greeting.txt", "Write-Output hello >> greeting.txt", "echo hello >> greeting.txt", "向 greeting.txt 追加 hello，而不是保留原文件完全不变。", "不同 Shell 的编码和换行不同，追加到不同编码文件时可能损坏文本。"),
    Example("删除测试文件", "rm demo.tmp", "Remove-Item -LiteralPath demo.tmp", "del demo.tmp", "删除当前目录中的 demo.tmp，此操作可能无法恢复。", "别名、错误提示和回收机制不同；只在专用测试目录确认目标后尝试。"),
)


def gradio_examples() -> list[list[str]]:
    # Cover all six directed Shell pairs in the UI.
    pairs = ((Shell.BASH, Shell.POWERSHELL), (Shell.POWERSHELL, Shell.CMD), (Shell.CMD, Shell.BASH),
             (Shell.BASH, Shell.CMD), (Shell.POWERSHELL, Shell.BASH), (Shell.CMD, Shell.POWERSHELL))
    return [[example.command_for(pairs[i % 6][0]), pairs[i % 6][0].value, pairs[i % 6][1].value, Mode.CONVERT.value]
            for i, example in enumerate(EXAMPLES)]
