# 启动与演示手册

本文是项目运行说明，不是实验报告。

## 本机启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Windows 可使用 README 中的 PowerShell 命令。访问 http://127.0.0.1:7860 。
默认没有模型配置时运行离线演示；应用不会执行输入的 Shell 命令。

## 三种模型模式

- `SHELLGUARD_BACKEND=mock`：无需密钥，12 组示例对照与静态规则，可演示页面，不算真实大模型效果。
- `SHELLGUARD_BACKEND=real`：在 `.env` 同时填写 `MODEL_API_KEY`、`MODEL_BASE_URL`、`MODEL_NAME`。适用于支持现有消息接口的模型供应商。
- `SHELLGUARD_BACKEND=local`：安装 `pip install -r requirements-local.txt`，设置 `LOCAL_MODEL` 为模型名或本地权重路径。首次运行可能下载权重；支持 CPU，GPU 更适合课堂现场演示。

使用已训练的 LoRA 时，再设置 `LOCAL_ADAPTER=training_outputs/qwen25-05b-shellguard/final_adapter`，并确保 `LOCAL_MODEL` 与训练使用的基础模型一致。基础模型和 adapter 必须同时存在；首次请求加载模型，同一进程串行执行本地推理。
切换模式或配置后需要重启服务。页面显示当前模式，每次分析显示成功或失败。失败时静态检测仍可使用。

## Docker（离线 / API 模式）

需要安装 Docker Engine 与 Compose 插件。

```bash
cp .env.example .env
# 按需要编辑 .env 中模型配置和访问口令
docker compose up -d --build
docker compose ps
docker compose logs --tail=80 shellguard
```

访问 http://127.0.0.1:7860 。停止服务：`docker compose down`。
镜像不包含模型密钥、数据集或 GPU 训练依赖；本地 LoRA 使用上面的 Python 环境启动方式。

## 局域网与公网

Python 启动时将 `APP_HOST=0.0.0.0`；Docker 则设置 `APP_BIND_ADDRESS=0.0.0.0`。
同一局域网设备访问 `http://服务器局域网IP:7860`，需允许相应入站连接。
公网服务器建议只将容器端口发布到 127.0.0.1，并由 Nginx/Caddy 提供 HTTPS 反向代理，转发到 7860 端口；代理需支持长连接与流式响应。
在 `.env` 同时配置 `APP_USERNAME` 和 `APP_PASSWORD` 可开启登录（管理员账号），修改后重启。密码不要提交 Git。
开启登录后，登录页会带"注册"入口（`/register`），任何人都可以自助创建账号；账号保存在本地文件 `USERS_DB_PATH`（默认 `.runtime/users.json`，已在 `.gitignore`，密码经加盐哈希后存储，不是明文）。即使不配置 `APP_USERNAME`/`APP_PASSWORD`，只要曾经有人通过 `/register` 注册过账号，应用也会自动要求登录；全新部署、账号库为空且未配置管理员账号时保持当前的无需登录直接可用。`MAX_USERS`（默认 200）限制可注册账号数量，避免被脚本刷注册占满磁盘。
公网 URL 取决于实际服务器、域名和网络配置，本仓库不附虚构的线上地址或二维码。确认手机能访问真实 HTTPS 链接后再生成二维码用于展示。

## 课堂展示（约 3 分钟）

1. 展示页面模型模式，真实演示前先确认可成功调用模型。
2. 解释 `ls`，说明输入、模型解释与静态规则。
3. 将 `ls` 从 Bash 转为 PowerShell，展示 `Get-ChildItem` 和语义差异。
4. 风险分析 `rm -rf /`，展示严重风险及规则来源，不执行命令。
5. 恢复一条会话记录，下载 Markdown 与 JSON。
6. 如果已完成微调，展示训练清单与真实评估对比，再切换 LoRA 实际分析。

建议截图：完整首页、真实模型转换成功、严重风险、微调对比结果。截图保存在 `artifacts/screenshots/` 时应保留模式标识，离线截图不能标注为真实推理。

## 常见问题

- 页面打不开：检查启动日志、端口和监听地址；本机启动默认不允许外部访问。
- API 配置不完整：填写三个模型字段，或明确使用 mock。
- 模型返回格式异常：模型需遵循项目 JSON 输出协议，小模型需经微调和评估确认能力。
- 本地推理失败：确认依赖已安装、模型下载完成、adapter 匹配且内存足够。
- 下载按钮无文件：先完成分析，再在“复制与导出”点击“生成下载文件”。
- 会话记录：只在当前会话保留 20 条，不是持久化数据库；下载文件包含命令文本，请自行保管。

## 复现浏览器验收

先以离线模式启动服务（`SHELLGUARD_BACKEND=mock python app.py`），然后在另一终端运行：

```bash
pip install -r requirements-browser.txt
python -m playwright install chromium
python scripts/browser_smoke.py
```

Linux 如缺少 Chromium 系统库，可按 Playwright 提示安装浏览器依赖；中文截图需要系统安装中文字体。脚本覆盖转换、严重风险、文件下载、历史恢复、清空与手机布局，截图输出到 `artifacts/screenshots/`。
