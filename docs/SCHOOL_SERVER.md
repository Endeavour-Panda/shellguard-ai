# 学校 GPU 服务器部署与微调

脚本不包含 SSH 密码。需要先从校园网、VPN 或跳板机登录服务器。当前尚未实际连接学校服务器，下面是待执行流程，不是部署成功记录。

## 1. 获取项目与检查环境

```bash
git clone https://github.com/Endeavour-Panda/shellguard-ai.git
cd shellguard-ai
bash scripts/school_server.sh check
```

已克隆时进入原目录执行 `git pull --ff-only`。先确认 `nvidia-smi` 中 GPU 型号、显存占用和现有任务。不要停止其他人的进程。

## 2. 准备独立环境

优先激活学校已有的 CUDA/PyTorch 环境，再运行：

```bash
bash scripts/school_server.sh setup
```

脚本创建 `.venv-server`，允许复用当前 Python 环境中满足要求的包，新依赖安装到项目虚拟环境，不修改系统环境。若现有环境没有可用的 CUDA PyTorch，应先根据服务器驱动选择匹配的 PyTorch；不要在未检查驱动时直接升级全局环境。安装后会检查 CUDA 和可用显存。

默认使用 GPU 0，可通过 `export CUDA_VISIBLE_DEVICES=1` 选择其他可用 GPU。训练与 Web 推理都检查至少 6 GiB 空闲显存，该门槛不保证任何自定义大模型都能运行。

## 3. 跑通基础评估、LoRA、微调后评估

```bash
bash scripts/school_server.sh train
```

推荐在服务器的 tmux 会话内运行，避免 SSH 断开终止任务：`tmux new -s shellguard-train`，执行上述命令，按 Ctrl+B 再按 D 分离，`tmux attach -t shellguard-train` 恢复。

默认沿用项目的 `Qwen/Qwen2.5-0.5B-Instruct`，先验证完整流程；使用普通 LoRA、不做 4-bit 量化，避免小模型在 3090 上增加不必要的量化依赖。脚本按顺序完成基础模型评估、5 epoch 训练、adapter 评估和对比，任一步失败即停止。不要同时启动 Web 推理占用训练显存。

模型首次使用需要下载权重。若学校服务器无法访问模型仓库，可提前下载完整模型目录，并设置 `MODEL_ID=/实际模型目录`。切换模型前需重新核对显存需求。

每次运行保存在独立的 `training_outputs/server-时间戳/` 下，包括日志、环境版本、代码提交、基础评估、adapter、训练清单和对比表。脚本使用文件锁避免同一项目目录重复启动训练。

当前只有 24 条训练、8 条验证数据，验证集还参与最佳模型选择。这只适合验证管线，不能作为独立测试集效果结论。若微调没有提升，应保留实际结果，而不是改写指标。

## 4. 启动真实本地模型 Web

先启动基础模型验证推理：

```bash
bash scripts/school_server.sh serve
```

微调流水线完成时会打印包含本次 adapter 实际路径的启动命令。也可手动设置：

```bash
LOCAL_MODEL=Qwen/Qwen2.5-0.5B-Instruct \
LOCAL_ADAPTER=/完整路径/final_adapter \
bash scripts/school_server.sh serve
```

模型在首次请求时加载；必须实际完成一次分析，才能确认模型加载与 JSON 输出成功。小模型返回格式无效时，页面会保留静态检测，但不代表模型推理已成功。

默认 Web 仅监听服务器的 127.0.0.1:7860。在自己电脑另外建立 SSH 转发：

```bash
ssh -N -L 7860:127.0.0.1:7860 用户名@服务器地址
```

然后浏览器访问 http://127.0.0.1:7860 。这需要你的电脑能通过校园网或 VPN 到达服务器。

若需要同学直接通过校园网访问，配置 `APP_HOST=0.0.0.0`，并按学校规定开放 7860 端口；建议在服务器 `.env` 配置 `APP_USERNAME`、`APP_PASSWORD`。浏览器访问 `http://服务器内网IP:7860`。内网地址不能作为可从互联网访问的部署链接。
