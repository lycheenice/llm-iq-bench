# 测试 Skills

这里存放"如何评测某一维度"的可读技能说明（opencode 风格 markdown）。每个 skill 给出：探针设计、判分要点、常见坑、最小执行步骤。可被 agent 评测流程引用，也可供人直接阅读。

## 索引

| Skill | 维度 | 要点 |
|---|---|---|
| [knowledge-testing](knowledge-testing.md) | 知识广度 | 多选题 extraction、中英差异、天花板题 |
| [reasoning-testing](reasoning-testing.md) | 数学与推理 | answer extraction、多数采样、避免格式假阴 |
| [coding-testing](coding-testing.md) | 代码能力 | 沙箱执行、pass@k、SWE-bench 环境 |
| [safety-testing](safety-testing.md) | 安全 | 双向指标（拒绝率+过度拒绝率）、脱敏 |
| [long-context-testing](long-context-testing.md) | 长上下文 | 针的深度/位置、token 数报告 |
| [instruction-following-testing](instruction-following-testing.md) | 指令遵循 | 可验证指令、LLM-judge 固定裁判 |
| [agent-testing](agent-testing.md) | Agent | 工具环境方差、多次均值 |

## 使用

- 跑评测前阅读对应 skill，避免重蹈已知坑。
- 设计新探针时，遵循 skill 中的判分约定，保证跨模型可比。
- skill 与 `suites/<dim>/definition.yaml` 对应；改判分口径须同步两者。
