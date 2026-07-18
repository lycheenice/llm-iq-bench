---
name: agent-testing
dimension: agent
---

# Agent 评测 Skill

## 何时使用
评测工具调用正确性与端到端多步任务执行。

## 探针设计
- BFCL：给定函数 schema，测函数调用 JSON 的字段/类型正确性，含简单/并行/多轮。
- GAIA/τ-bench：真实多步任务，需联网/文件/工具，测最终成功率。

## 判分要点
- BFCL：解析输出 JSON，比对函数名与参数；可用执行结果二次校验。
- GAIA：最终答案精确匹配（官方 normalize 后比对）。
- 端到端任务**方差极大**，须多次（>=3）取均值并报标准差。

## 常见坑
- ❌ 用单次成功率：agent 任务单次结果噪声大，单分不可信。
- ❌ 工具环境不一致：网络可达性、文件状态会改变结果；须固定快照。
- ❌ 模型不输出 JSON 而输出自然语言就判全错：先尝试宽松解析（代码块/正则）再判。
- ❌ GAIA 给了工具就让模型自由发挥：需限步数/限 token 防失控。

## 最小执行
```bash
python scripts/run_benchmark.py run --plan plans/full/plan.yaml --model <id>  # 含 agent_bfcl/gaia
```

## 与本仓库映射
- 定义：`suites/agent/definition.yaml`
- runner：`function_exec` / `agent_loop`（骨架未实现，跳过）
