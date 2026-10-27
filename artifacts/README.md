# 项目验证材料

以下为早期离线验收记录；最新已完成的真实 GPU 训练与部署见 [AutoDL 实测材料](autodl/README.md)。

截图来自浏览器访问本机应用，使用 **离线模拟模式**，不代表真实大模型推理或 LoRA 实验成绩。

- [首页](screenshots/01-home.png)
- [跨 Shell 转换](screenshots/02-conversion.png)
- [严重风险检测](screenshots/03-risk.png)
- [手机布局](screenshots/04-mobile.png)

本次验证：47 项 pytest 测试通过；浏览器验收通过转换、风险分析、JSON 下载、历史恢复、清空和移动端宽度检查；训练数据校验通过（24 条训练、8 条验证，无重复请求交集）。

尚未验证：真实 API 请求、GPU 模型推理与 LoRA 训练、Docker 容器启动和公网访问。当前环境没有 Docker Compose 插件。复现步骤见 [启动说明](../docs/DEPLOYMENT.md)，浏览器脚本位于 `scripts/browser_smoke.py`。
