# 跨 Run 对比

共 5 次 run（来自 `reports/runs/*.json`，按模型→时间排序）。

## 总览

| Run | 模型 | 方案 | 标签 | 时间 | 综合 |
|---|---|---|---|---|---|
| coding_robust__glm-local | glm-local | coding_robust | — | 20260718T163755Z | 0.452 |
| local_v1__glm-local | glm-local | local_v1 | — | 20260718T163755Z | 0.707 |
| needle_stress__glm-local | glm-local | needle_stress | — | 20260718T163755Z | 0.667 |
| coding_robust__glm-local | glm-local | coding_robust | — | 20260718T171259Z | 0.648 |
| local_v1__glm-local | glm-local | local_v1 | — | 20260718T171259Z | 0.808 |

## 各任务得分

| Run | 模型 | coding_humaneval_t02 | coding_mbpp_t02 | coding_humaneval | coding_mbpp | agent_bfcl | long_needle | long_needle_stress |
|---|---|---|---|---|---|---|---|---|
| coding_robust__glm-local | glm-local | 0.838 | 0.067 | — | — | — | — | — |
| local_v1__glm-local | glm-local | — | — | 0.823 | 0.090 | 0.917 | 1.000 | — |
| needle_stress__glm-local | glm-local | — | — | — | — | — | — | 0.667 |
| coding_robust__glm-local | glm-local | 0.812 | 0.483 | — | — | — | — | — |
| local_v1__glm-local | glm-local | — | — | 0.854 | 0.460 | 0.917 | 1.000 | — |

## 按模型聚合（同模型多次 run 取最新）

| 模型 | 最新综合 | 任务数 |
|---|---|---|
| glm-local | 0.648 | 2 |

_由 reporter.build_comparison 生成于 2026-07-18T17:35:41+00:00。_