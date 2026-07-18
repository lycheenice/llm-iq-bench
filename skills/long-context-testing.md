---
name: long-context-testing
dimension: long_context
---

# 长上下文评测 Skill

## 何时使用
评测模型在长文档内的信息检索与综合能力。

## 探针设计
- Needle-in-a-Haystack：把一句"针"插入长文本某深度/位置，问针内容，测召回。
- LongBench/RULER：真实长文档 QA，测 F1/EM。

## 判分要点
- Needle：答案精确匹配（EM），按**深度×位置**网格多次取样，报平均召回。
- LongBench：用 F1（token 级），中文按字、英文按词。
- 文档长度按模型 `context_length` 自适应，**报告实际 token 数**，否则跨模型不可比。

## 常见坑
- ❌ 只测一个深度：单点召回不代表长上下文能力，必须网格化。
- ❌ 不报 token 数：不同分词器下"4k 文档"差异巨大。
- ❌ 用 HF 默认截断静默截掉针：须显式控制输入长度 < 上下文上限的 90%。
- ❌ Needle 答案在 prompt 里就出现（抄写泄漏）：确保问的是针的属性而非针本身。

## 最小执行
```bash
python scripts/run_benchmark.py run --plan plans/full/plan.yaml --model <id>  # 含 long_needle/long_longbench
```

## 与本仓库映射
- 定义：`suites/long_context/definition.yaml`
- 指标：`exact_match_text`（Needle）/ `f1`（LongBench）
