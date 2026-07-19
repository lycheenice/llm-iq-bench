# 设计：多采样评测（maj@1 / pass@k）

> P0-1。修复 AIME `n:4` 死代码，让 `bench.params.n` 真正生效；
> 同时为后续 HumanEval/MBPP `pass@k` 无偏估计（P1）打基础。

## 问题

`configs/benchmarks.yaml` 中 `reasoning_aime` 声明 `params: {n: 4, temperature: 0.7}`，
但 `runner._run_one` 走单采样路径 `client.generate()`（`src/llm_iq_bench/runner.py:127`），
`models._openai_generate` 虽把 `n` 写进 body（`models.py:98-99`），
却 `return choices[0]`（`models.py:106`）—— 烧 4× token，只取第 1 条，
pass@k / self-consistency 完全没生效。

## 目标

1. `bench.params.n > 1` 时，runner 改调 `client.generate_n(prompt, n)`，拿到 n 条预测。
2. 提供两种聚合口径，由 `bench.aggregator` 字段选择：
   - `maj@1`（默认，self-consistency）：n 条答案里出现次数最多的算最终答案；平票取首个。
   - `pass@k`：n 条里**任一**答案正确即判对（k = n）。
3. 单采样（`n` 缺省或 =1）走原路径，行为不变。
4. samples.jsonl 每题记录 `n_predictions`（list）+ `aggregator` + 最终 `verdict`。

## 接口

### `metric` 层加 `maj_at_1`

`src/llm_iq_bench/metrics.py`：
```python
def maj_at_1(predictions: list[str], gold, **ctx) -> bool:
    """n 条预测做 answer extraction 后多数投票，比对 gold。"""
    extractor = ctx.get("extractor")  # "last_number" / "boxed" / None
    normed = [_extract(p, extractor) for p in predictions]
    counts = Counter(normed)
    top = counts.most_common(1)[0][0]  # 平票时 most_common 取首个出现顺序
    return _eq(top, gold)
```
注意：`maj_at_1` 签名与其它 metric 不同（接 list 而非 str），只在 runner 多采样分支调用，
**不注册进 `METRICS` dict**（避免单采样路径误用）。

### `runner._run_one` 多采样分支

```python
n_samples = params.pop("n", 1)
if n_samples and n_samples > 1:
    preds = client.generate_n(prompt, n_samples, **params)
    agg = bench.get("aggregator", "maj@1")
    verdict = aggregate(agg, preds, gold, extractor, ctx)
    # samples 记 preds 列表
else:
    pred = client.generate(prompt, **params)   # 原路径
    ...
```

`aggregate("maj@1", ...)` 调 `metrics.maj_at_1`；
`aggregate("pass@k", ...)` 调逐条 metric，任一 True 即 True。

### `bench.aggregator` 字段

`benchmarks.yaml` 显式声明：
- `reasoning_aime`: `aggregator: maj@1`（self-consistency 惯例）
- P1 再加 `coding_humaneval_pk`: `n:5, aggregator: pass@k`

## 边界与不变量

- `generate_n` 对 mock provider 返回 n 条独立随机（`models.py:36-37` 已实现），不依赖外部。
- 多采样分支只走「非 runner」路径（reasoning 类）；`runner=code_exec` 等执行器自行管 `n`，P1 再统一。
- 平票：`Counter.most_common` 在同计数时保留**首次出现顺序**，可复现。
- `pass@k` 用 k=n（当前 n 即采样数）；P1 的无偏估计 `pass@k = 1 - C(n-c,n-k)/C(n,n)` 留到 HumanEval。

## 测试要点（tests/test_multi_sample.py）

1. `maj_at_1` 多数票：`["42","42","7"]` gold="42" → True；`["7","42","7"]` gold="42" → False；平票取首。
2. `aggregate pass@k`：n 条里任一对即 True。
3. mock client `generate_n` 返回 n 条且长度==n。
4. 集成：mock + `reasoning_aime` 配置，跑 1 题，samples.jsonl 含 `n_predictions` 且 `verdict` 非空；
   normalize 后 `len(n_predictions)==4`。
5. 单采样路径不变：`n` 缺省时 `samples.jsonl` 不含 `n_predictions` 字段（向后兼容）。

## 验收

- `python3 tests/_runner.py` 全绿（含新 5 条）。
- `reasoning_aime` mock 集成跑通：每题写出 4 条预测。
- 现有 `quick`/`local_v1` plan 行为不变（无 `n` 字段的任务走单采样原路径）。
