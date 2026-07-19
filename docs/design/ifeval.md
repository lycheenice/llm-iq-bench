# 设计：IFEval 执行器（指令遵循逐条校验）

> P0-5。让 `instruction_following` 维度从 errored 变可跑。
> 落地 `executors.run_ifeval` + `ifeval_checker`，strict/loose 两档；
> 提供 builtin mini-IFEval 样本供离线验证（HF 不可达环境也能跑）。

## 问题

`metrics.ifeval_strict` 是 `raise NotImplementedError` 的 stub（`metrics.py:76`），
`benchmarks.yaml` 的 `ifeval_strict` 无 `runner` 字段 → 当前被 P0-2 errored 探针拦截。
IFEval 的判分逻辑是「逐条可验证指令校验」（不是简单 EM），必须用专用执行器。

## 目标

1. 新增 `ifeval` runner：`executors.run_ifeval`，负责加载样本、调模型、逐条校验、聚分。
2. 新增 `src/llm_iq_bench/ifeval_checker.py`：独立指令校验器（strict + loose 两档），纯函数，可单测。
3. `benchmarks.yaml` 的 `ifeval_strict` 加 `runner: ifeval`，dispatch 加分支。
4. builtin mini-IFEval 数据集：`builtin:ifeval_mini`，6–10 条覆盖关键指令类型，离线验证用。
5. metric `ifeval_strict` 不再被探针当成未实现（runner 分支绕过 metrics 路径）。

## IFEval 判分逻辑

每条样本含 `prompt` + `instructions`（list of `{instruction_id, kwargs}`）。
模型输出 `response`。对每条指令用对应 check 函数判 pass/fail。
- **strict**：指令必须严格满足（如「不超过 3 句」精确计数）。
- **loose**：放宽一格（如 ≤4 句也算 pass），用于惩罚性较低的评估。
任务级 score = 通过指令数 / 总指令数（按指令计，非按样本）。

### 支持的指令类型（mini 版子集，对齐官方 IFEval）
- `length_constraint:num_sentences`：strict = 句数==kwargs["num_sentences"]；loose = ±1
- `length_constraint:num_words`：strict = 词数==kwargs["num_words"]；loose = ±5%
- `detectable_format:number_bullet_lists`：strict = 以"N. "开头的行数==kwargs["num_bullets"]
- `detectable_format:json_format`：strict = 整个响应是合法 JSON 对象
- `punctuation:no_comma`：strict = 响应不含逗号
- `startend:quotation`：strict = 整个响应被双引号包裹
- `case:capital_word`：strict = 每个词首字母大写
- `language:chinese_only`：strict = 不含 ASCII 字母（中文场景）

未识别 instruction_id → 该指令-mcp 标 fail（不崩）。

## 接口

### `ifeval_checker.check_instruction(instruction_id, kwargs, response, strict=True) -> bool`
注册表 `INSTRUCTION_CHECKS` dict 映射 id → 函数。未识别返回 False。

### `ifeval_checker.score_response(response, instructions, strict=True) -> dict`
返回 `{"passed": int, "total": int, "details": [{id, passed}]}`。

### `executors.run_ifeval(runner, bench, spec, n, samples_file)`
- 用 `load_dataset_samples` 取样本
- 每样本：`render("raw", sample)` → `client.generate` → `score_response` strict
- score = Σpassed / Σtotal（跨样本所有指令）
- samples 每条写 `{prompt, prediction, instructions, strict_pass_rate, verdict}`
- 返回 `{"metric":"ifeval_strict","score":...,"n":n,"total":total,"aggregator":"per_instruction"}`
- 同时算 loose 分，记入 outcome 的 `score_loose`（供报告参照）

### dispatch 加分支
`executors.dispatch` 加 `if runner_kind == "ifeval": return run_ifeval(...)`。
`_NOT_IMPLEMENTED_RUNNERS` 不含 ifeval（它现在实现）。

### builtin mini-IFEval
`datasets.py._load_builtin` 加 `builtin:ifeval_mini` 分支，返回 8 条样本，
每条带 `prompt` + `instructions` 字段。`configs/datasets.yaml` 加 `ifeval` 条目
（source=huggingface, repo=google/IFEval）+ `ifeval_mini`（source=builtin）。
`benchmarks.yaml` 的 `ifeval_strict.dataset` 保持 `ifeval`（真实评测），
但离线验证用临时把 dataset 指向 `ifeval_mini` 的方式（单测里 patch）。

## 边界与不变量

- runner=ifeval 绕过 metrics.py 的 `ifeval_strict` stub（executors 全权处理）。
- strict/loose 都算，主 score 用 strict，loose 进 outcome 不进 summary 主分。
- 未识别 instruction_id 标 fail 不崩（forward-compat 官方新指令）。
- builtin 样本可纯 python 跑（无 HF/网络）。
- mock 模型输出固定文本，mini-IFEval 上能产出可预期分数（验证管道通畅）。

## 测试要点（tests/test_ifeval.py）

1. `check_instruction` 各指令类型 strict pass/fail 各一例。
2. `score_response` 多指令聚合正确。
3. 未识别 id → False，不崩。
4. loose 比 strict 宽（至少一例）。
5. `run_ifeval` 集成：mock + ifeval_mini，产出非空 score，samples 含 verdict。
6. dispatch("ifeval", ...) 路由到 run_ifeval。

## 验收

- `python3 tests/_runner.py` 全绿（新增 ≥6 条）。
- mock + mini-IFEval 端到端：`score` 非零非 None，`samples.jsonl` 有逐条记录。
- `plans/L1_screening` 的 `ifeval_strict` 不再 errored（因有 runner=ifeval）——
  注：L1 真实跑需 GLM 在线，P0 只验证 mock + mini。

## 后续（P1）

- 接真实 `google/IFEval` 全量 541 条（需 HF 库 + 网络）。
- loose 分进 summary 二级指标。
- 多语言指令（中文 IFEval 变体）。
