# 公网演示材料

访问：[ShellGuard AI](https://8ba1ea41a7112e6e6c.gradio.live)

![访问二维码](shellguard-qr.png)

二维码仅包含网址，已用独立的 zxing-cpp 解码器核对。用户名 `student`，使用当前 Web 密码；密码不随材料发布。

2026-10-27 09:28 UTC 从外网 Chromium 实测完成：HTTPS 登录、1.5B LoRA 模型页面、真实本地模型响应、带空格文件名转换、严重风险提示、JSON 下载。命令均未执行。检查清单见 [verification.json](verification.json)。

- [登录页截图](00-public-login.png)
- [手机页面截图](04-public-mobile.png)
- [首页截图](01-public-home.png)
- [转换截图](02-public-conversion.png)
- [风险截图](03-public-risk.png)
- [真实下载的分析结果](browser-download.json)
- [可打印 SVG 二维码](shellguard-qr.svg)

这是临时 Gradio 分享链接，约一周后失效，应用重启也可能改变链接；服务器必须开机运行。使用者应在演示前检查此地址。详见 [部署操作说明](../../docs/AUTODL_DEPLOYED.md)。

转换结果采用模型和规则结合，页面明确标记来源；有限合成测试的 32/32 不代表模型原始转换准确率。原始成绩及局限见 [实验说明](../../docs/CONVERSION_V3.md)。

页面采用深蓝与青绿配色，登录页、首页及页尾均标注“李振昊创作 · 燕山大学”。手机布局按 390px 宽度进行实测，页面无横向溢出。
