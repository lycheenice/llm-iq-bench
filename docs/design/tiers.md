# 设计：测试分级 L0–L3

> P0-4。把现有 `quick`/`full` 二元收敛为四级，每级明确时间预算×样本量×维度覆盖×温度策略。
> 配合 P1 的 composer 按 `--time-budget` 动态产 plan。

## 问题

当前 `plans/` 有 7 个 plan（quick/full/chinese/reasoning_deep/local_v1/coding_robust/needle_stress），
无统一分级语义：`quick` 只是冒烟、`full` 是全量，但中间档（快速排序/初筛）缺失，
用户无法按"我只有 30 分钟"或"我要正式对比"灵活选择，各 plan 的样本量与维度覆盖也无矩阵对照。

## 目标

定义四级，plan 顶层加 `tier` 字段（`L0`/`L1`/`L2`/`L3`）+ `time_budget_min` 估值。

| 级别 | 时间 | 用途 | 维度覆盖 | 每任务 n | 温度 | 重复 | seed |
|---|---|---|---|---|---|---|---|
| **L0 smoke** | <1 min | 离线冒烟/CI | knowledge+reasoning demo only | 6 | 0 | 1 | 固定 |
| **L1 screening** | ~20 min | 快速排序/初筛 | 8 维各 1 代表任务 | 30 | 0（AIME 0.7×4） | 1 | 固定 |
| **L2 standard** | ~2 h | 正式对比基准 | 8 维全量代表集 | 200–500 | 0（AIME 0.7×4） | 1 | 固定 |
| **L3 deep** | ≥8 h | 深度/天花板 | L2 + SWE-bench + GAIA + MT-Bench + 多语言全集 | 全量 n_default | 含 t=0.2 鲁棒性 | 3 | 固定 |

### L1 代表任务（8 维各 1，全部当前可跑或 P0-5 后可跑）
- knowledge: `knowledge_mmlu`
- reasoning: `reasoning_gsm8k`
- coding: `coding_humaneval`
- instruction_following: `ifeval_strict`（P0-5 落地后可跑；之前 errored）
- safety: `safety_advbench`
- agent: `agent_bfcl`
- multilingual: `multilingual_mgsm`
- long_context: `long_needle`

## 落地

### 新建 4 个 plan 文件
- `plans/L0_smoke/plan.yaml`：tier=L0，mock/内置，`demo_mc`+`demo_qa`（替代旧 `quick` 的 mock 用途）
- `plans/L1_screening/plan.yaml`：tier=L1，n=30，8 维代表；`model: glm-local`（本机默认）
- `plans/L2_standard/plan.yaml`：tier=L2，n=200–500，8 维代表集；`model: glm-local`
- `plans/L3_deep/plan.yaml`：tier=L3，全量 + SWE/GAIA/MT-Bench stub（标注 `skipped`/`errored` 直到落地）；`model: glm-local`

每个 plan 顶层加：
```yaml
tier: L1
time_budget_min: 20
seed: 1234
```

### 旧 plan 处置
- `plans/quick`：保留，标 `tier: L0`（等价 L0_smoke，向后兼容 `make demo`）
- `plans/full`：保留，标 `tier: L2`（L2 的英文 cloud 版本，model=gpt-4o-mini）
- `plans/chinese`/`reasoning_deep`/`local_v1`/`coding_robust`/`needle_stress`：加 `tier` 标注（专项，归 L2/L3 语义）

### methodology.md 加分级矩阵章节
新增「## 测试分级」段落，含上表 + 各级适用场景 + 复现说明（同 tier+同 seed+同 version 才可对比）。

## 边界与不变量

- L0 必须零依赖：mock + builtin 数据，无网络/无 HF/无 docker。`make demo` 仍走 quick（=L0）。
- L1/L2 的 `model: glm-local` 指本机 sglang；用户可改 plan 的 model 字段或 CLI `--model` 覆盖。
- L3 的 stub 任务（swe_bench/gaia/mt_bench）会被 runner 标 errored/skipped，不阻塞其余任务。
- tier 字段是信息性元数据，runner 不因此改变行为；P1 composer 会按 tier 选 n。

## 验证

1. `python3 scripts/run_benchmark.py run --plan plans/L0_smoke/plan.yaml --model mock` 端到端跑通，无 skip/errored（demo 任务可跑）。
2. `plans/L1_screening` 的 8 个 benchmark id 在 `configs/benchmarks.yaml` 都能找到。
3. methodology.md 出现「测试分级」段落与矩阵。
4. 旧 `plans/quick` 加 `tier: L0` 后 `make demo` 仍正常。

> L1/L2/L3 的真实模型跑分不在 P0 验证范围（需 GLM/API 在线）；P0 只验证结构正确与 L0 离线跑通。
