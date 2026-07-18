---
name: reasoning-testing
dimension: reasoning
---

# 数学与推理评测 Skill

## 何时使用
评测多步算术、竞赛数学、符号/逻辑推理。

## 探针设计
- prompt 末尾固定要求 `Put the final answer in \boxed{}`，便于抽取。
- 基础题（GSM8K/ARC）`temperature=0`；高方差难题（AIME）`temperature=0.7, n>=4`，取任一正确或多数投票。

## 判分要点
- 三档 extractor：
  1. `boxed`：抓 `\boxed{...}` 最后一个；
  2. `last_number`：取文本最后一个数字（GSM8K 数字题）；
  3. `exact_match_text`：BBH 等文本答案。
- 数字比对前统一去千分位逗号、去小数尾零：`1,000` / `1000.0` 都应等价 `1000`。
- MATH 答案可能含 `\frac`、`\sqrt`：骨架阶段用文本规整近似，正式评测建议用 `math_verify` 或官方 `answer_check`。

## 常见坑
- ❌ 不做 answer extraction 直接比全文：CoT 解说里的中间数字会污染匹配。
- ❌ AIME 只跑一次取 0/1：方差极大，单次分不可比；必须 pass@k 或 majority。
- ❌ 把"过程对但最终答案错"判对：本维度只看最终答案准确性。

## 最小执行
```bash
python scripts/run_benchmark.py run --plan plans/reasoning_deep/plan.yaml --model <id>
```

## 与本仓库映射
- 定义：`suites/reasoning/definition.yaml`
- 指标：`exact_match_numeric` / `exact_match_boxed` / `exact_match_text`
- prompt：`prompts.reasoning_qa`
