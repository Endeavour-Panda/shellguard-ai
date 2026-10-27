"""Conservative, reviewed mappings for a small literal-command grammar.

This is not a general shell parser. Reject expansion, control operators, paths,
wildcards and unknown flags; leave those cases to the model and user review.
"""

import re
import shlex

from src.schemas import Shell


def _literal(value: str) -> bool:
    return bool(re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_. -]*', value)) and not value.endswith((' ', '.'))


def _quote(value: str, shell: Shell) -> str:
    if ' ' not in value:
        return value
    return f'"{value}"' if shell == Shell.CMD else f"'{value}'"


def convert_known_command(command: str, source: Shell, target: Shell) -> str | None:
    """Convert only recognized literal forms; output is never executed."""
    if source == target:
        return command
    value = command.strip()
    for name, ps, cmd in [('HOME', '$HOME', '%USERPROFILE%'), ('PATH', '$env:PATH', '%PATH%')]:
        forms = {
            Shell.BASH: [f'echo "${name}"', f'echo ${name}', f'printf "%s\\n" "${name}"', f"printf '%s\\n' \"${name}\""],
            Shell.POWERSHELL: [ps, f'Write-Output {ps}', f'echo {ps}'],
            Shell.CMD: [f'echo {cmd}'],
        }
        matches = value in forms[source] if source == Shell.BASH else value.lower() in [x.lower() for x in forms[source]]
        if matches:
            return {Shell.BASH: f'printf "%s\\n" "${name}"', Shell.POWERSHELL: f'Write-Output {ps}', Shell.CMD: f'echo {cmd}'}[target]
    if re.search(r'[\n\r\t$%!`&|;<>*?\\/()\[\]{}]', value):
        return None
    # Limit tokens to plain words or whole quoted literals. No concatenated quotes.
    token_pattern = r'''(?:"[A-Za-z0-9_. -]+"|'[A-Za-z0-9_. -]+'|[A-Za-z0-9_.-]+)'''
    if not re.fullmatch(token_pattern + r'(?: +' + token_pattern + r')*', value):
        return None
    if source == Shell.CMD and "'" in value:
        return None  # CMD does not use single quotes for grouping.
    try:
        tokens = shlex.split(value)
    except ValueError:
        return None
    head = tokens[0] if source == Shell.BASH else tokens[0].lower()
    rest = tokens[1:]
    simple = {
        Shell.BASH: {'ls': 'list', 'pwd': 'pwd'},
        Shell.POWERSHELL: {'get-childitem': 'list', 'get-location': 'pwd'},
        Shell.CMD: {'dir': 'list', 'cd': 'pwd'},
    }
    forms = {
        'list': {Shell.BASH: 'ls', Shell.POWERSHELL: 'Get-ChildItem', Shell.CMD: 'dir'},
        'pwd': {Shell.BASH: 'pwd', Shell.POWERSHELL: 'Get-Location', Shell.CMD: 'cd'},
    }
    if head in simple[source] and not rest:
        return forms[simple[source][head]][target]
    operation = None
    if source == Shell.BASH:
        operation = {'cat':'read', 'cp':'copy', 'mv':'move', 'mkdir':'mkdir', 'echo':'echo'}.get(head)
    elif source == Shell.CMD:
        operation = {'type':'read', 'copy':'copy', 'move':'move', 'mkdir':'mkdir', 'echo':'echo'}.get(head)
    else:
        lower = [x.lower() for x in rest]
        if head == 'get-content' and len(rest) == 2 and lower[0] == '-literalpath':
            operation, rest = 'read', [rest[1]]
        elif head in ('copy-item', 'move-item') and len(rest) == 4 and lower[0] == '-literalpath' and lower[2] == '-destination':
            operation, rest = ('copy' if head == 'copy-item' else 'move'), [rest[1], rest[3]]
        elif head == 'new-item' and len(rest) == 4 and lower[:3] == ['-itemtype', 'directory', '-path']:
            operation, rest = 'mkdir', [rest[3]]
        elif head == 'write-output':
            operation = 'echo'
    count = 2 if operation in ('copy', 'move') else 1
    if operation is None or len(rest) != count or not all(_literal(x) for x in rest):
        return None
    # Reserved device names and CMD echo switches are not plain files/text.
    if any(x.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]} for x in rest):
        return None
    if operation == 'echo' and rest[0].lower() in ('on', 'off'):
        return None
    args = [_quote(x, target) for x in rest]
    a = args[0]
    b = args[1] if len(args) == 2 else ''
    commands = {
        'read': {Shell.BASH:f'cat {a}', Shell.POWERSHELL:f'Get-Content -LiteralPath {a}', Shell.CMD:f'type {a}'},
        'copy': {Shell.BASH:f'cp {a} {b}', Shell.POWERSHELL:f'Copy-Item -LiteralPath {a} -Destination {b}', Shell.CMD:f'copy {a} {b}'},
        'move': {Shell.BASH:f'mv {a} {b}', Shell.POWERSHELL:f'Move-Item -LiteralPath {a} -Destination {b}', Shell.CMD:f'move {a} {b}'},
        'mkdir': {Shell.BASH:f'mkdir {a}', Shell.POWERSHELL:f'New-Item -ItemType Directory -Path {a}', Shell.CMD:f'mkdir {a}'},
        'echo': {Shell.BASH:f'echo {a}', Shell.POWERSHELL:f'Write-Output {a}', Shell.CMD:f'echo {a}'},
    }
    # CMD echo retains quote characters, unlike Bash/PowerShell.
    if operation == 'echo' and (' ' in rest[0] or '"' in value or "'" in value):
        return None
    return commands[operation][target]
