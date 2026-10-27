"""Run against a local offline demo: pip install playwright; playwright install chromium."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    output = Path('artifacts/screenshots')
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1100})
        page.goto('http://127.0.0.1:7860', wait_until='domcontentloaded')
        analyze = page.get_by_role('button', name='分析命令', exact=True)
        analyze.wait_for()
        expect(page.get_by_text('离线演示', exact=True)).to_be_visible()
        page.screenshot(path=str(output / '01-home.png'), full_page=True)
        command = page.get_by_label('命令文本', exact=True)
        command.fill('ls')
        page.get_by_role('radio', name='跨 Shell 转换', exact=True).check()
        analyze.click()
        expect(page.locator('#result-panel')).to_contain_text('Get-ChildItem')
        page.screenshot(path=str(output / '02-conversion.png'), full_page=True)
        command.fill('rm -rf /')
        page.get_by_role('radio', name='风险分析', exact=True).check()
        analyze.click()
        expect(page.locator('#result-panel')).to_contain_text('总风险：严重')
        page.screenshot(path=str(output / '03-risk.png'), full_page=True)
        page.get_by_role('tab', name='复制与导出', exact=True).click()
        page.get_by_role('button', name='生成下载文件', exact=True).click()
        download_link = page.get_by_role('button', name='下载 JSON', exact=True)
        expect(download_link).to_be_enabled()
        with page.expect_download() as download:
            download_link.click()
        saved = output.parent / 'download-check.json'
        download.value.save_as(saved)
        payload = json.loads(saved.read_text())
        assert payload['request']['command'] == 'rm -rf /'
        assert payload['overall_risk'] == 'critical'
        saved.unlink()
        page.get_by_text('本次会话记录', exact=True).click()
        picker = page.get_by_label('选择记录以恢复输入与结果', exact=True)
        picker.click()
        page.get_by_role('option').filter(has_text='· ls').click()
        expect(command).to_have_value('ls')
        page.get_by_role('tab', name='可读分析', exact=True).click()
        expect(page.locator('#result-panel')).to_contain_text('Get-ChildItem')
        page.get_by_role('button', name='清空输入与结果', exact=True).click()
        expect(command).to_have_value('')
        expect(page.locator('#result-panel')).to_contain_text('输入命令并点击')
        mobile = browser.new_page(viewport={'width':390, 'height':844}, is_mobile=True)
        mobile.goto('http://127.0.0.1:7860', wait_until='domcontentloaded')
        mobile.get_by_role('button', name='分析命令', exact=True).wait_for()
        assert mobile.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        mobile.screenshot(path=str(output / '04-mobile.png'), full_page=True)
        browser.close()
    print('PASS: conversion, critical risk, JSON download, history restore, clear, mobile layout')


if __name__ == '__main__':
    main()
