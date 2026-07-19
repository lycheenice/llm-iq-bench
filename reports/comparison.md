# 跨 Run 对比

共 5 次 run（来自 `reports/runs/*.json`，按模型→时间排序）。

## 总览

| Run | 模型 | 方案 | 标签 | 时间 | 综合 |
|---|---|---|---|---|---|
| needle_stress__glm-local | glm-local | needle_stress | — | 20260718T163755Z | 0.667 |
| coding_robust__glm-local | glm-local | coding_robust | — | 20260718T171259Z | 0.648 |
| local_v1__glm-local | glm-local | local_v1 | — | 20260718T171259Z | 0.808 |
| local_v1__glm-local | glm-local | local_v1 | — | 20260719T013258Z | 0.809 |
| local_v1__glm-local | glm-local | local_v1 | — | 20260719T013300Z | 0.803 |

## 各任务得分

| Run | 模型 | coding_humaneval_t02 | coding_mbpp_t02 | coding_humaneval | coding_mbpp | agent_bfcl | long_needle | long_needle_stress |
|---|---|---|---|---|---|---|---|---|
| needle_stress__glm-local | glm-local | — | — | — | — | — | — | 0.667 |
| coding_robust__glm-local | glm-local | 0.812 | 0.483 | — | — | — | — | — |
| local_v1__glm-local | glm-local | — | — | 0.854 | 0.460 | 0.917 | 1.000 | — |
| local_v1__glm-local | glm-local | — | — | 0.860 | 0.460 | 0.917 | 1.000 | — |
| local_v1__glm-local | glm-local | — | — | 0.835 | 0.460 | 0.917 | 1.000 | — |

## 按模型聚合（同模型多次 run 取最新）

| 模型 | 最新综合 | 任务数 |
|---|---|---|
| glm-local | 0.803 | 4 |

_由 reporter.build_comparison 生成于 2026-07-19T02:01:39+00:00。_