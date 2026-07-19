# 评测报告 — glm-local

- 方案: `L1_screening`
- 模型: `glm-local`
- 时间: 20260719T165927Z
- 原始结果: `results/L1_screening_glm-local_20260719T165927Z/`
- 综合得分（已跑任务均分）: **0.740**

## 任务明细

| 任务 | 指标 | 得分 | 样本数 | 状态 |
|---|---|---|---|---|
| reasoning_gsm8k | exact_match_numeric | 0.433 | 30 | OK |
| reasoning_bbh_navigate | exact_match_text | 1.000 | 20 | OK |
| coding_humaneval | pass_at_1 | 0.900 | 30 | OK |
| coding_mbpp | pass_at_1 | 0.567 | 30 | OK |
| agent_bfcl | function_call_accuracy | 0.867 | 30 | OK |
| long_needle | exact_match_text | 1.000 | 9 | OK |
| ifeval_mini_strict | ifeval_strict | 0.800 | 8 | OK |
| multilingual_mgsm | exact_match_numeric | 0.350 | 20 | OK |

_自动生成于 2026-07-19T17:23:08+00:00，由 reporter.emit_run_report 写入。_