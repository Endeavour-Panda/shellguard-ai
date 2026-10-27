"""Compare different model sizes on identical frozen cases, raw and hybrid.

Strict string equality is intentionally retained. These figures are not a
claim of executable or arbitrary semantic equivalence.
"""
import argparse
import json
from pathlib import Path
from src.schemas import Shell
from src.shell_converter import convert_known_command
from training.metrics import summarize


def report(path):
    raw = json.loads(path.read_text())
    rows = json.loads(json.dumps(raw['records']))
    rules = 0
    for row in rows:
        if row['parsed'] is not None:
            r = row['request']
            converted = convert_known_command(r['command'], Shell(r['source_shell']), Shell(r['target_shell']))
            if converted is not None:
                row['parsed']['converted_command'] = converted
                rules += 1
    return {'model': raw['model'], 'adapter':raw['adapter'], 'raw_model': summarize(raw['records']), 'application_with_current_rules':summarize(rows), 'rule_overrides':rules}, raw


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--before',type=Path,required=True)
    parser.add_argument('--after',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    before, a=report(args.before); after,b=report(args.after)
    assert a['eval_sha256']==b['eval_sha256'], 'Different evaluation file hashes'
    assert [(r['request'],r['expected']) for r in a['records']]==[(r['request'],r['expected']) for r in b['records']], 'Different cases'
    result={'eval_sha256':a['eval_sha256'], 'before':before,'after':after,'limitations':'32 synthetic in-family cases, exact command match. Invalid JSON counts as failure. New rules applied separately to BOTH models. No command executed. No evidence of general script equivalence.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
