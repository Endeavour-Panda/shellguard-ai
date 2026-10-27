"""Verify a deployed public page without storing the login password."""
import argparse
import getpass
import json
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

parser=argparse.ArgumentParser()
parser.add_argument('--url',required=True)
parser.add_argument('--username',default='student')
parser.add_argument('--output-dir',type=Path,default=Path('artifacts/public'))
args=parser.parse_args()
password=getpass.getpass('Web login password: ')
out=args.output_dir
out.mkdir(parents=True,exist_ok=True)
checks=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1100})
    page.goto(args.url,wait_until='domcontentloaded',timeout=60000)
    page.get_by_role('textbox',name='username',exact=True).wait_for()
    expect(page.locator('body')).to_contain_text('李振昊创作')
    page.screenshot(path=str(out/'00-public-login.png'),full_page=True)
    page.get_by_role('textbox',name='username',exact=True).fill(args.username)
    page.get_by_role('textbox',name='password',exact=True).fill(password)
    page.get_by_role('button',name='Login',exact=True).click()
    analyze=page.get_by_role('button',name='分析命令',exact=True)
    analyze.wait_for(timeout=60000)
    expect(page.locator('body')).to_contain_text('Qwen2.5-1.5B-Instruct')
    expect(page.locator('body')).to_contain_text('燕山大学')
    expect(page.locator('body')).to_contain_text('李振昊创作')
    checks.append('HTTPS login, creator attribution and Qwen2.5-1.5B LoRA page')
    page.screenshot(path=str(out/'01-public-home.png'),full_page=True)
    command=page.get_by_label('命令文本',exact=True)
    command.fill('cat "quarter report.txt"')
    page.get_by_role('radio',name='跨 Shell 转换',exact=True).check()
    analyze.click()
    expect(page.locator('#analysis-summary')).to_contain_text('分析完成',timeout=180000)
    expect(page.locator('#result-panel')).to_contain_text("Get-Content -LiteralPath 'quarter report.txt'")
    expect(page.locator('#result-panel')).to_contain_text('本地模型已返回')
    expect(page.locator('#result-panel')).to_contain_text('确定性内置规则')
    page.screenshot(path=str(out/'02-public-conversion.png'),full_page=True)
    checks.append('Live local-model response plus quoted-filename conversion')
    command.fill('rm -rf /')
    page.get_by_role('radio',name='风险分析',exact=True).check()
    analyze.click()
    expect(page.locator('#result-panel')).to_contain_text('总风险：严重',timeout=180000)
    expect(page.locator('#result-panel')).to_contain_text('本地模型已返回')
    page.screenshot(path=str(out/'03-public-risk.png'),full_page=True)
    checks.append('Critical-risk analysis without executing command')
    page.get_by_role('tab',name='复制与导出',exact=True).click()
    page.get_by_role('button',name='生成下载文件',exact=True).click()
    download=page.get_by_role('button',name='下载 JSON',exact=True)
    expect(download).to_be_enabled(timeout=60000)
    with page.expect_download(timeout=60000) as event:
        download.click()
    saved=out/'browser-download.json'
    event.value.save_as(saved)
    data=json.loads(saved.read_text())
    assert data['backend']=='local' and data['model'] is not None
    assert data['overall_risk']=='critical'
    checks.append('Authenticated JSON download')
    page.set_viewport_size({'width':390,'height':844})
    page.reload(wait_until='domcontentloaded')
    page.get_by_role('button',name='分析命令',exact=True).wait_for(timeout=60000)
    expect(page.locator('body')).to_contain_text('李振昊创作')
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 2'), 'Mobile page overflow'
    source_box=page.locator('#input-panel').bounding_box()
    result_box=page.locator('#output-panel').bounding_box()
    assert source_box and result_box and result_box['y'] >= source_box['y'] + source_box['height'] - 2, 'Mobile panels must stack vertically'
    page.screenshot(path=str(out/'04-public-mobile.png'),full_page=True)
    checks.append('Mobile 390px layout without horizontal page overflow')
    browser.close()
(out/'verification.json').write_text(json.dumps({'url':args.url,'verified_at':datetime.now(timezone.utc).isoformat(),'checks':checks},ensure_ascii=False,indent=2))
print('PASS:',', '.join(checks))
