# 设计：多轮评测稳定性对比

> P1。同一 plan 用不同 seed 跑 N 轮，验证复现性 + 测服务端/管道方差。

## 目标

1. 新增 `scripts/run_multi.py`：跑同一 plan N 轮（不同 seed），每轮独立 run_dir。
2. 跑完用 `reporter.build_comparison` 或新 `build_variance_report` 聚合。
3. temp=0 任务理论上应跨 seed 完全一致（验证 sglang greedy 确定性）；任何差异 → 标红。
4. 输出方差表：每任务各轮得分/均值/极差/标准差。

## 接口

```bash
python scripts/run_multi.py --plan plans/glm_full_v2/plan.yaml \
  --model glm-local --rounds 3 --seeds 1234,5678,9012
```

- 每轮：`Runner(seed=si).run_plan(plan)` → run_dir_i
- 跑完扫描 N 个 run_dir 的 summary.json，调 `reporter.build_variance_report`。
- 方差报告 md 含：各任务 N 轮得分表 + 极差 + 标准差 + 稳定性结论。

## 边界

- temp=0 任务跨 seed 应 0 方差（理论）；实测非 0 → 标注「服务端非确定性」。
- temp>0 任务（AIME n=4）跨 seed 应有方差（预期）。
- 本 plan 全 temp=0，3 轮应高度一致；若有差异，反映 sglang 服务的微小非确定性。

## 测试要点

- `build_variance_report` 纯函数单测：造 3 个 summary，验证极差/标准差计算。
- 排除 skipped/errored 任务。
- 不同 plan/不同任务集的 run 不应混入（按 plan name 过滤）。

## 验收

- 3 轮全跑通，每轮 8 任务无 skip/errored。
- 方差报告生成，temp=0 任务极差 ≤ 0.05（5%）视为稳定。
- 全量单测绿。
