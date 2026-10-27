# ShellGuard AI

ShellGuard AI 是一个基于 Python、Gradio 和 OpenAI 兼容 API 的 Shell 命令文本分析工具。它解释命令、提供 Bash、PowerShell、CMD 之间的转换建议，并把模型判断与静态风险规则分开呈现。应用不会执行用户命令，也不会把输出描述为已经验证。

## 本次完善

新增双栏分析工作台、会话历史恢复、Markdown/JSON 文件下载、可选登录、Docker 部署和本地基础模型/LoRA 推理入口。具体操作见 [启动与演示手册](docs/DEPLOYMENT.md)。学校 GPU 服务器上的部署与微调流程见 [学校服务器操作指南](docs/SCHOOL_SERVER.md)。

实际完成的 AutoDL 训练与部署见 [运行管理说明](docs/AUTODL_DEPLOYED.md) 和 [真实评估与截图](artifacts/autodl/README.md)。

## 启动

Python 3.10 或更新版本：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

浏览器打开 `http://127.0.0.1:7860`。默认只监听本机，不创建公网分享链接。可用 `APP_HOST`、`APP_PORT` 修改监听地址和端口。将 `APP_HOST` 设为 `0.0.0.0` 只会监听所有网卡；是否可由外网访问仍取决于服务器防火墙和网络配置，不代表已部署。

## 模型 API 配置

在本机 `.env` 文件或进程环境变量中设置：

```dotenv
MODEL_API_KEY=
MODEL_BASE_URL=
MODEL_NAME=
SHELLGUARD_BACKEND=auto
```

请按所选供应商的文档填写完整 OpenAI 兼容 API 根地址和模型名；程序不会猜测 `/v1` 路径。`auto` 仅在三个模型字段全空时启用离线模拟，字段全部齐全时才发送真实请求，部分配置会报错。`mock` 强制离线，`real` 要求完整配置。远程地址须使用 HTTPS，本机回环地址允许 HTTP。密钥不会在界面显示；不要提交 `.env`。

离线模式提供 12 组手写样例对照，不做通用命令推理。对未知输入，解释和转换会明确标记为不可用，只运行静态文本规则。高风险静态规则可独立工作。真实请求包含命令文本，请勿发送密码、令牌或敏感路径。

## 页面使用

选择“命令解释”“跨 Shell 转换”或“风险分析”，再选择源 Shell。转换模式可设置目标 Shell。输入命令或选择示例后点击“分析命令”；结果分别列出总体风险、模型解释、转换建议、语义差异、验证建议及原始/转换文本各自命中的静态规则。转换命令会注明未经验证。

“复制与导出”和 JSON 结果区域提供复制按钮，并可下载 Markdown/JSON 文件。会话历史最多保留 20 条，可恢复输入及结果。“清空输入与结果”会清空命令及分析。页面包含 12 个示例，文件操作只应在已准备好的测试目录中人工审阅。

## 风险规则边界

静态扫描是保守的正则启发式，不是完整 Shell 解析器。它会检测删除和宽泛删除、磁盘写入、覆盖、远程下载后执行、嵌套求值、管道/连接符、变量与命令替换、引号转义、路径、权限和部分 CMD 批处理差异。注释、字符串中的文本可能造成误报，别名、间接展开及混淆可能漏报。没有命中不等于安全；模型的低风险判断也不是安全认证。请人工核对版本、变量、当前目录、路径及影响范围，并在隔离测试环境验证。

## 测试

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

测试使用模拟客户端，不访问真实模型 API。若运行环境没有模型配置，不应把模拟测试结果解释为真实调用成功。

## 服务器 LoRA 微调

DashScope 的 `qwen-plus` 是托管 API，不能下载权重直接做 LoRA。本项目默认使用同系列开源模型 `Qwen/Qwen2.5-0.5B-Instruct` 在服务器上验证微调流程，基础模型可通过 `--model` 切换。训练只读取命令文本，从不执行数据中的命令。

推荐使用 AutoDL 的 PyTorch 2.x 镜像、Python 3.10/3.11 和至少 8 GB 显存。将项目上传到服务器后执行：

```bash
cd /root/ShellGuard-AI
python -m venv .venv-train
source .venv-train/bin/activate
python -m pip install -U pip
python -m pip install -r requirements-train.txt
python -m training.validate_data
```

先评估基础模型，再训练 LoRA，最后使用同一评估集评估 adapter：

```bash
python -m training.evaluate \
  --model Qwen/Qwen2.5-0.5B-Instruct \
  --output training_outputs/base_eval.json

python -m training.train_lora \
  --model Qwen/Qwen2.5-0.5B-Instruct \
  --output-dir training_outputs/qwen25-05b-shellguard

python -m training.evaluate \
  --model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter training_outputs/qwen25-05b-shellguard/final_adapter \
  --output training_outputs/lora_eval.json
```

训练脚本默认使用 NF4 量化、LoRA rank 8、alpha 16、5 个 epoch，只对 assistant 的结构化答案计算损失。`training_manifest.json` 会记录基础模型、数据 SHA256、参数、GPU 和训练指标。当前种子数据用于验证流程，不足以证明生产质量；正式实验应继续人工审核扩充，并根据独立测试集比较 JSON 有效率、风险等级准确率和转换命令精确匹配率。

AutoDL 上传和运行步骤见 [training/AUTODL.md](training/AUTODL.md)。

## 微调模型接回 Web 与结果对比

完成上述训练后，在安装了 `requirements-local.txt` 的环境中设置：

```dotenv
SHELLGUARD_BACKEND=local
LOCAL_MODEL=Qwen/Qwen2.5-0.5B-Instruct
LOCAL_ADAPTER=training_outputs/qwen25-05b-shellguard/final_adapter
```

重启 `python app.py`，页面会显示“本地推理 · LoRA 微调模型”。留空 `LOCAL_ADAPTER` 可运行基础模型。

```bash
python -m training.compare \
  --base training_outputs/base_eval.json \
  --tuned training_outputs/lora_eval.json \
  --output training_outputs/comparison.md
```

比较工具校验两次评估的基础模型、请求和标注是否一致，重新计算指标；无效 JSON 也计入转换任务分母。现有 eval 数据同时用于训练中的模型选择，因此结果应称为验证集结果；正式泛化评估需另外准备不参与训练与模型选择的独立测试集，再通过 `training.evaluate --eval-file` 评估。仓库不会预置虚构的训练成绩。
