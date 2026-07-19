# 评测报告 — glm-local

- 方案: `glm_full_v2`
- 模型: `glm-local`
- 时间: 20260719T111015Z
- 原始结果: `results/glm_full_v2_glm-local_20260719T111015Z/`
- 综合得分（已跑任务均分）: **0.719**

## 任务明细

| 任务 | 指标 | 得分 | 样本数 | 状态 |
|---|---|---|---|---|
| reasoning_gsm8k | exact_match_numeric | 0.433 | 30 | OK |
| coding_humaneval | pass_at_1 | 0.867 | 30 | OK |
| coding_mbpp | pass_at_1 | 0.433 | 30 | OK |
| agent_bfcl | function_call_accuracy | 0.867 | 30 | OK |
| long_needle | exact_match_text | 1.000 | 9 | OK |
| ifeval_mini_strict | ifeval_strict | 0.800 | 8 | OK |
| multilingual_mgsm | exact_match_numeric | 0.350 | 20 | OK |
| reasoning_bbh_navigate | exact_match_text | 1.000 | 20 | OK |

_自动生成于 2026-07-19T11:32:44+00:00，由 reporter.emit_run_report 写入。_