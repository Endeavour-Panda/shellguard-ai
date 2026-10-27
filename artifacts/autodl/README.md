# AutoDL 真实训练与部署材料

当前为第三轮 1.5B LoRA 版本，详见 [实测说明](../../docs/CONVERSION_V3.md)、[原始对比](autodl2080ti-v3/comparison.json) 和 [公网截图/二维码](../public/README.md)。以下为前两轮历史记录。

2026-10-27 在单张 RTX 2080 Ti 11 GB 上运行。模型为 Qwen2.5-0.5B-Instruct，FP16 普通 LoRA，rank 8、alpha 16、学习率 2e-4、batch size 1、梯度累积 8。数据为 24 条训练和 8 条验证。

| 指标 | 基础模型 | 5 epoch LoRA | 20 epoch LoRA |
| --- | ---: | ---: | ---: |
| JSON 有效率 | 12.5% | 87.5% | 87.5% |
| 风险等级准确率 | 0% | 37.5% | 50% |
| 转换精确匹配率 | 0% | 0% | 0% |

第二轮重用第一轮的基础模型评估（同一模型、数据、FP16 与生成长度），没有重复生成基础成绩。两轮原始输出均保留。20 epoch 运行结束后，Trainer 按验证损失选中 checkpoint-33（第 11 epoch）作为 final_adapter，当时 Web 部署使用该 adapter，现已切换第三轮。

验证集参与了 checkpoint 和部署版本选择，样本量也很小；以上不是独立测试集成绩。首轮 Web 中 ls 转换格式无效，第二轮 ls、rm -rf /、pwd 均返回有效结构化分析。转换精确匹配仍为 0，模型输出需要人工复核，不能宣称转换正确率已经达到可用标准。

- [第一轮结果](autodl2080ti-v1/comparison.md)
- [第二轮结果](autodl2080ti-v2/comparison.md)
- [真实模型 Web 验收记录](autodl2080ti-v2/web_smoke.json)
- [部署首页截图](screenshots/01-deployed-home.png)
- [真实模型转换截图](screenshots/02-local-lora-conversion.png)
- [严重风险截图](screenshots/03-local-lora-risk.png)

截图通过 SSH 隧道访问真实服务器生成，页面保持“本地推理 · LoRA 微调模型”标识，不是离线模拟。浏览器验收通过登录、模型分析、严重风险显示和 JSON 下载；生成命令没有被执行。

训练源码对应 GitHub 提交 `4dafc2b`，源码树为 `2eba0e4663e069ed2dc0a3362b9702214a85914d`。服务器因网络问题通过 git am 同步，训练时记录的提交 SHA 与 GitHub SHA 可能不同，但源码树一致；后续已对齐提交元数据。

完整 adapter 与日志保存在服务器 training_outputs/ 下，并已备份至开发工作区 training_outputs/autodl-experiment-backup.tar.gz。模型权重、登录密码和 .env 均不提交 GitHub。
