# AutoDL 实际部署操作说明

项目目录：`/root/autodl-tmp/shellguard-ai`。模型目录：`/root/autodl-tmp/models/Qwen2.5-1.5B-Instruct`。
当前 Web 使用 `training_outputs/autodl2080ti-v3/lora/final_adapter`，监听 `0.0.0.0:6006`，由独立 Supervisor 进程管理。登录用户名为 `student`，当前密码仅保存在服务器 `.env`，文件权限为 600。
登录页现在带"注册"入口，学生也可以自助创建账号；账号文件默认存在项目目录下的 `.runtime/users.json`（裸机部署下随进程用户正常继承读写权限，无需额外配置）。

## 访问

**已验证公网地址（2026-10-30）：https://affdf83b411c5778fa.gradio.live**

[当前二维码 PNG](../artifacts/public/current/shellguard-qr.png) · [当前二维码 SVG](../artifacts/public/current/shellguard-qr.svg) · [手机登录验收记录](../artifacts/public/current/mobile-login-verification.json)

不需要建立 SSH 隧道即可访问。用户名仍为 `student`，使用服务器当前配置的 Web 密码。公网浏览器已验证登录、本地模型分析、带空格文件名转换、严重风险提示和 JSON 下载。

这是 Gradio 临时分享链接，官方说明有效期约 1 周；实例必须保持运行，应用重启后链接可能变化。它不是永久域名。到期或重启后从 `logs/web.log` 查找最新 `Running on public URL`，重新生成二维码；不要复用旧二维码。分享设置为 `.env` 中 `APP_SHARE=true`。若要长期固定入口，使用 AutoDL 控制台提供的 6006 自定义服务地址，或另配域名和反向代理。


可以从 AutoDL 控制台打开该实例 6006 端口的“自定义服务”。实际公网映射地址由控制台提供，本次尚未验证该映射。

已验证的方式是在自己的电脑建立 SSH 隧道：

```bash
ssh -N -L 6006:127.0.0.1:6006 -p 你的SSH端口 root@你的实例SSH域名
```

保持终端连接，在浏览器访问 http://127.0.0.1:6006 。在服务器终端查看 Web 登录密码：

```bash
cd /root/autodl-tmp/shellguard-ai
grep '^APP_PASSWORD=' .env
```

Web 密码与 SSH 密码不同。修改 `.env` 后重启 Web 即可生效。

## 服务管理

```bash
cd /root/autodl-tmp/shellguard-ai
bash scripts/autodl_service.sh status
bash scripts/autodl_service.sh logs
bash scripts/autodl_service.sh restart
bash scripts/autodl_service.sh stop
bash scripts/autodl_service.sh start
```

Supervisor 会在应用异常退出后重启应用；SSH 断开不会停止服务。实例关机后不提供访问，重新开机后需执行 start；尚未配置实例开机自动启动任务。

若在新镜像中复现，创建项目虚拟环境并安装 requirements-train.txt，再安装 `supervisor>=4.2,<5`；确认 CUDA 可用并准备基础模型、adapter 和 `.env` 后再启动。配置模板位于 deploy/autodl-supervisord.conf，只适用于上面的部署路径，其他目录需要相应修改。

## 实验材料

当前第三轮：Qwen2.5-1.5B-Instruct，197 条训练、18 条验证、32 条保留测试，5 epoch，选择 checkpoint-125。详见 [转换与微调说明](CONVERSION_V3.md)。历史第一轮 5 epoch、第二轮 20 epoch 的材料也完整保留。完整记录见 [真实实验材料](../artifacts/autodl/README.md)。本次使用普通 LoRA 和 FP16，并非 4-bit QLoRA；没有调用远程模型 API。

服务器保留三轮模型和日志。前两轮备份为 `/root/autodl-tmp/shellguard-experiment-backup.tar.gz`，第三轮备份为 `/root/autodl-tmp/shellguard-v3-backup.tar.gz`。释放实例前应下载该文件；GitHub 中只保存轻量评估记录和截图，不保存 adapter 权重。

## 公网组件与二维码复现

本实例无法直接下载 Gradio 的 frpc 组件，因此从 Gradio 提示的官方地址 `https://cdn-media.huggingface.co/frpc-gradio-0.3/frpc_linux_amd64` 下载后上传，安装至 `/root/.cache/huggingface/gradio/frpc/frpc_linux_amd64_v0.3`，权限 755。该文件 SHA-256 为 `c791d1f047b41ff5885772fc4bf20b797c6059bbd82abb9e31de15e55d6a57c4`。未修改 TLS 校验，也未将组件或凭据提交 GitHub。

```bash
python -m pip install -r requirements-qr.txt
python scripts/make_public_qr.py https://你的最新地址.gradio.live
```

二维码只编码网址，没有登录密码。可在教室展示二维码后单独告知老师 Web 登录口令。
