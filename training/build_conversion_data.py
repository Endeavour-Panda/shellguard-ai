"""Build reproducible synthetic SFT data. Templates do not execute commands.

Splits use distinct literal names; the test measures in-family generalization,
not arbitrary shell-script equivalence. Original evaluation requests are kept
out of training. Labels are specified here independently of runtime rules.
"""
import json
from pathlib import Path
from itertools import permutations
from training.validate_data import validate_pair, fingerprint

SHELLS = ['Bash', 'PowerShell', 'CMD']
MODE = '跨 Shell 转换'
ROOT = Path('data/conversion_v3')

def quote(s, shell):
    return ('"'+s+'"' if shell == 'CMD' else "'"+s+"'") if ' ' in s else s

def forms(kind, name):
    a = [quote(name, s) for s in SHELLS]
    b = [quote('backup_'+name, s) for s in SHELLS]
    return dict(zip(SHELLS, {
        'read': [f'cat {a[0]}', f'Get-Content -LiteralPath {a[1]}', f'type {a[2]}'],
        'copy': [f'cp {a[0]} {b[0]}', f'Copy-Item -LiteralPath {a[1]} -Destination {b[1]}', f'copy {a[2]} {b[2]}'],
        'move': [f'mv {a[0]} {b[0]}', f'Move-Item -LiteralPath {a[1]} -Destination {b[1]}', f'move {a[2]} {b[2]}'],
        'mkdir': [f'mkdir {a[0]}', f'New-Item -ItemType Directory -Path {a[1]}', f'mkdir {a[2]}'],
        'echo': [f'echo {a[0]}', f'Write-Output {a[1]}', f'echo {a[2]}'],
        'list': ['ls', 'Get-ChildItem', 'dir'],
        'pwd': ['pwd', 'Get-Location', 'cd'],
    }[kind]))

def record(kind, name, source, target):
    cmds = forms(kind, name)
    risk = 'medium' if kind in ('copy','move','mkdir') else 'low'
    explanation = {'read':'读取指定文本文件的内容。','copy':'复制指定文件到目标名称，目标已存在时可能覆盖。','move':'移动或重命名指定文件，需核对目标是否已存在。','mkdir':'创建指定目录。','echo':'输出给定文本。','list':'列出当前目录的项目。','pwd':'显示当前工作目录。'}[kind]
    return {'request': {'command':cmds[source], 'source_shell':source, 'target_shell':target, 'mode':MODE}, 'answer': {'explanation':explanation, 'converted_command':cmds[target], 'risk_level':risk, 'risk_reasons':['可能改变文件系统；需确认目录及目标是否已存在。'] if risk=='medium' else [], 'semantic_differences':['转换对应常见用途；输出格式、文本编码、隐藏项及覆盖交互可能不同，不保证字节级等价。'], 'validation_suggestions':['在隔离测试目录中人工核对文件名、工作目录、目标 Shell 版本及输出。']}}

def key(row):
    return json.dumps(row['request'], ensure_ascii=False, sort_keys=True)

def main():
    ROOT.mkdir(exist_ok=True)
    old_train = [json.loads(x) for x in Path('data/shellguard_train.jsonl').read_text().splitlines() if x.strip()]
    old_eval = [json.loads(x) for x in Path('data/shellguard_eval.jsonl').read_text().splitlines() if x.strip()]
    blocked = {key(x) for x in old_eval}
    datasets = {'train':old_train, 'validation':[], 'test':[]}
    pairs = list(permutations(SHELLS, 2))
    for kind in ('read','copy','move','mkdir'):
        for name in ('notes_a.txt','report_b.csv','log_c.txt','draft d.txt','sample_e.txt','project_f'):
            datasets['train'] += [record(kind,name,*pair) for pair in pairs]
        datasets['validation'] += [record(kind,'validation paper.txt',*pair) for pair in pairs[:3]]
        datasets['test'] += [record(kind,'holdout budget.txt',*pair) for pair in pairs]
    for kind in ('list','pwd'):
        datasets['train'] += [record(kind,'unused',*pair) for pair in pairs]
    for name in ('hello','ready','complete'):
        datasets['train'] += [record('echo',name,*pair) for pair in pairs]
    datasets['validation'] += [record('echo','validation',*pair) for pair in pairs]
    datasets['test'] += [record('echo','holdout',*pair) for pair in pairs]
    # Whitespace variants probe basic robustness. Not used for checkpoint selection.
    for kind in ('list','pwd'):
        row = record(kind,'unused','Bash','PowerShell'); row['request']['command'] = '  '+row['request']['command']+'  '
        datasets['test'].append(row)
    for split, rows in datasets.items():
        unique = {key(x):x for x in rows if split != 'train' or key(x) not in blocked}
        (ROOT/f'{split}.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in unique.values()))
    validate_pair(ROOT/'train.jsonl',ROOT/'validation.jsonl')
    validate_pair(ROOT/'train.jsonl',ROOT/'test.jsonl')
    validate_pair(ROOT/'validation.jsonl',ROOT/'test.jsonl')
    manifest = {s:{'count':len((ROOT/f'{s}.jsonl').read_text().splitlines()), 'sha256':fingerprint(ROOT/f'{s}.jsonl')} for s in datasets}
    manifest['limitations'] = 'Synthetic, same-family literal-command split. Does not establish arbitrary shell equivalence. Legacy validation excluded from training. Test not used for checkpoint selection.'
    (ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(json.dumps(manifest,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
