# 设计：可复现性（配置冻结 + seed 贯通 + errored 标记）

> P0-2 + P0-3。让每次 run 可复现、不可实现的任务不再误报 0 分。

## 问题

1. `runner.run_plan` 只写 `samples.jsonl + summary.json`，不冻结 plan/configs —— 改 yaml 后历史 run 无法复现。
2. plan 无 `seed`；`_openai_generate` body 不含 seed —— temp>0 任务（AIME/coding_robust）每次漂移。
3. `runner._run_one` 捕获 `NotImplementedError` 后 `verdict=None`、`scored+=0`，若整任务全 NotImplemented → `scored=0` → `score=0.0`，与"真实 0 分"无法区分；reporter 还把它算进综合得分分母（`reporter.py:51`）。

## 目标

### P0-2 errored 标记
- 任务级：若 `metric` 抛 `NotImplementedError` 且无 `runner` 兜底 → outcome 标 `{"errored": True, "reason": "metric not implemented: <name>"}`，**不**进 `scored`。
- reporter 综合得分：分母剔除 `skipped` 与 `errored`，只算真正跑分任务。
- summary 的 `_print_summary` 把 errored 与 skipped 分开打印。

### P0-3 配置冻结
- 每次 run 在 `run_dir/` 额外写 `config_snapshot.yaml`，含：
  - `plan`（完整 plan dict）
  - `models`（该 run 用的 model 条目；api_key 脱敏只留尾 4 位）
  - `datasets`（涉及的 dataset 条目）
  - `benchmarks`（涉及的 benchmark 条目）
  - `git`（commit hash + dirty 标记 + branch）
  - `seed`（plan 顶层或 CLI 传入）
  - `timestamp` / `runner_version`
- `plan` 顶层可加 `seed: <int>`；CLI `--seed` 覆盖；缺省走 `default_seed`（按 plan name 哈希，固定可复现）。

### seed 贯通
- `ModelClient` 新增 `seed` 属性（`build_model_client` 透传）。
- `_openai_generate` / `_openai_tools` 把 `seed` 写进 body（OpenAI/sglang/vllm 均支持字段名 `seed`，OpenAI best-effort）。
- runner 把 `seed` 注入每次 `generate*/generate_with_tools` 的 params（executors 的 `gen_params` 也注入）。
- mock provider：用 `seed` 初始化 `random.Random`，使 mock 输出可复现（现 `models.py:80` 用 `hash(prompt)`，改为 `hash((prompt,seed))`）。
- needle_gen / bfcl 等执行器内部 `rng` 也用 plan seed（现硬编码 `seed=42` / `Random(0)`，改为 `params.get("seed", plan_seed)`）。

## 接口

### `runner.run_plan` 加快照
```python
snapshot = {
    "plan": plan,
    "model": {model_id: models_cfg[model_id] + 脱敏},
    "datasets": {id: cfg for 涉及的},
    "benchmarks": {id: cfg for 涉及的},
    "git": _git_info(),   # {"commit","dirty","branch"}
    "seed": seed,
    "timestamp": ts,
    "runner_version": __version__,
}
(run_dir / "config_snapshot.yaml").write_text(yaml.safe_dump(snapshot, ...))
```

### seed 解析
```python
seed = plan.get("seed")
if seed is None and cli_seed is not None: seed = cli_seed
if seed is None: seed = _default_seed(plan["name"])  # 稳定哈希
```

### `_run_one` errored 分支
现有 `try: verdict = compute_metric(...) except NotImplementedError: verdict=None` 之外，
新增：在循环开始前先探针 `compute_metric` 是否实现（用空输入触发），若整任务 metric 未实现且无 runner → 直接返回 `errored` outcome，不进 samples。
更稳：保留逐题跑，但若某题 `NotImplementedError` 即记 `errored`，整任务若有任何 errored 题 → outcome 加 `errored:True` + `score=None`。

**选择简化方案**：在 `_run_one` 非 runner 分支开始处做一次 `compute_metric(metric, "", None)` 探针；
抛 `NotImplementedError` → 返回 `{"errored":True,"reason":...}` 不跑题。
避免逐题空转。

### reporter 综合得分
`_render_run_md` 与 `build_comparison` 的 overall 计算，分母改为
`[t for t in tasks.values() if not skipped and not errored and "score" in t]`。

### executors seed 注入
`executors.run_needle_gen` 现 `seed = params.get("seed", 42)` → 改默认从 runner.seed 拿。
做法：dispatch 时把 `runner.seed` 注入 `bench["params"]["seed"]`（若未设）。
`run_function_exec` 的 `Random(0)` 抽样 → `Random(seed)`。

## 边界与不变量

- `config_snapshot.yaml` 中 `api_key` 脱敏：`"***"+key[-4:] if len(key)>4 else "***"`；空则 `"EMPTY"`。
- git 不可用（无 .git）时 `git_info` 返回 `{"commit": None, "dirty": None}` 不抛。
- seed 注入对 mock 生效：同 seed 同 prompt → 同输出（可复现单测）。
- errored 任务不进 `samples.jsonl`（不空写），summary 仍记录。
- 向后兼容：旧 plan 无 `seed` 字段 → 走 `_default_seed(plan_name)`，固定值，仍可复现。

## 测试要点（tests/test_reproducibility.py）

1. `_git_info()` 返回 dict 含 `commit`/`dirty` 键（即便无 git 也不抛）。
2. `_default_seed("quick") == _default_seed("quick")`（稳定）；不同 name 不同。
3. `_mask_key("sk-abcdef1234")` → `"***1234"`；空串 → `"***"`。
4. errored：构造 metric=`ifeval_strict`（未实现）的 bench，`_run_one` 返回 `errored:True`、`score` 缺失或 None。
5. config_snapshot：mock 跑 quick 1 题，`run_dir/config_snapshot.yaml` 存在，含 `plan/models/git/seed` 键，`api_key` 已脱敏。
6. seed 贯通 mock：同 seed 跑同一 prompt 两次，`generate` 输出一致（mock 用 seed）。
7. reporter 综合得分剔除 errored/skipped：构造 summary 含 errored 任务，overall 只算非 errored/skipped。

## 验收

- `python3 tests/_runner.py` 全绿（新增 ≥7 条）。
- `results/quick_mock_*/config_snapshot.yaml` 存在且含 git commit + 脱敏 api_key + seed。
- mock 下两次同 seed 同 plan 同 prompt 输出一致。
- `ifeval_strict`（未实现 metric）在 mock quick 里不再报 0 分，而是 errored。

> 注：P0-5 会落地 IFEval 执行器，届时 ifeval_strict 转为可跑。本 P0 阶段保持 errored 行为正确即可。
