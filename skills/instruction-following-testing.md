---
name: instruction-following-testing
dimension: instruction_following
---

# 指令遵循评测 Skill

## 何时使用
评测可验证格式约束与多轮对话质量。

## 探针设计
- IFEval：每条带若干可机械验证的指令（如"以#开头""少于3段""含至少两个关键词"）。
- MT-Bench：两轮开放问答，GPT-4 判 1-10 分。

## 判分要点
- IFEval 分 strict（精确满足）/ loose（等价满足）两档，各报指令级准确率。
- LLM-judge：**固定裁判模型 + prompt + temperature=0**，报告裁判版本；跨次可比性依赖裁判不变。
- 胜率类（AlpacaEval）：相对 baseline 的胜率，需固定 baseline。

## 常见坑
- ❌ 把 IFEval 当选择题跑：它需要逐条指令校验函数，不能用通用指标。
- ❌ 换裁判后继续刷分：跨裁判分数不可比，须重跑。
- ❌ MT-Bench 只取单轮：漏掉多轮连贯维度，应取第二轮分单独报。

## 最小执行
```bash
python scripts/run_benchmark.py run --plan plans/full/plan.yaml --model <id>  # 含 ifeval_strict/mt_bench
```

## 与本仓库映射
- 定义：`suites/instruction_following/definition.yaml`
- 指标：`ifeval_strict` / `llm_judge`（骨架未实现，跳过）
