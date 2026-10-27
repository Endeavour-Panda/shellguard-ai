# AutoDL 实际部署操作说明

项目目录：`/root/autodl-tmp/shellguard-ai`。模型目录：`/root/autodl-tmp/models/Qwen2.5-0.5B-Instruct`。
当前 Web 使用 `training_outputs/autodl2080ti-v2/lora/final_adapter`，监听 `0.0.0.0:6006`，由独立 Supervisor 进程管理。登录用户名为 `student`，随机生成的密码仅保存在服务器 `.env`，文件权限为 600。

## 访问

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

第一轮 5 epoch，第二轮 20 epoch；第二轮最终使用验证损失最低的第 11 epoch checkpoint。完整记录见 [真实实验材料](../artifacts/autodl/README.md)。本次使用普通 LoRA 和 FP16，并非 4-bit QLoRA；没有调用远程模型 API。

服务器保留两轮模型和日志，额外备份文件为 `/root/autodl-tmp/shellguard-experiment-backup.tar.gz`。释放实例前应下载该文件；GitHub 中只保存轻量评估记录和截图，不保存 adapter 权重。
