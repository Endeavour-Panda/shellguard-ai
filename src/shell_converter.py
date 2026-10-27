"""Small deterministic conversions for unambiguous, low-risk commands."""

import re

from src.schemas import Shell


def convert_known_command(command: str, source: Shell, target: Shell) -> str | None:
    """Return a reviewed mapping, or None when the exact semantics are unknown."""
    if source == target:
        return command

    normalized = command.strip()
    home_readers = {
        Shell.BASH: (r'echo\s+(["\'])?\$HOME\1', r'printf\s+["\']%s\\n["\']\s+["\']\$HOME["\']'),
        Shell.POWERSHELL: (r'(?:Write-Output|echo)\s+\$HOME',),
        Shell.CMD: (r'echo\s+%USERPROFILE%',),
    }
    if any(re.fullmatch(pattern, normalized, re.IGNORECASE) for pattern in home_readers[source]):
        return {
            Shell.BASH: 'printf "%s\\n" "$HOME"',
            Shell.POWERSHELL: "Write-Output $HOME",
            Shell.CMD: "echo %USERPROFILE%",
        }[target]
    return None
