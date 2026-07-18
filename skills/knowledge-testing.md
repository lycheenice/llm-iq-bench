---
name: knowledge-testing
dimension: knowledge
---

# 知识广度评测 Skill

## 何时使用
当需要评测模型跨学科事实性知识（STEM/人文/社科）时。

## 探针设计
- 统一为多选题（A-D 或 A-J），强制 `temperature=0, max_tokens=16` 防止跑题。
- 英文用 MMLU / MMLU-Pro / GPQA；中文用 C-Eval / CMMLU / AGIEval。
- 天花板探测用 GPQA / MMLU-Pro（10 选项、研究生级）。

## 判分要点
- 模型可能输出 "The answer is B" 或 "B. ..."：用 `accuracy_mc` 指标，先匹配行首字母，再回退匹配选项文本。
- 永远先抽 letter 再比对，避免把含 "B" 的长解释误判。
- 多语言场景注意选项字母是否本地化（中文题仍用 A-D）。

## 常见坑
- ❌ 直接比首字符：模型输出 "\n\nB" 会失败。应 strip 后取首个非空 token 的首字母。
- ❌ 混合 4/10 选项集训练偏置：MMLU-Pro 10 选项须单独报。
- ❌ 用全量 MMLU 当快速评测：耗时巨大，快速方案 n<=200 即可排序。

## 最小执行
```bash
python scripts/run_benchmark.py run --plan plans/quick/plan.yaml --model <id>
# 或单维
python scripts/run_benchmark.py run --plan plans/reasoning_deep/plan.yaml --model <id>  # 含 GPQA
```

## 与本仓库映射
- 定义：`suites/knowledge/definition.yaml`
- 指标：`metrics.accuracy_mc`
- prompt：`prompts.knowledge_mc` / `knowledge_mc_cn`
