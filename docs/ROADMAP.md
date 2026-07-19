# llm-iq-bench 路线图

> 2026-07-19 制定。基于代码实读诊断，把"能跑但松散"的工具收敛为
> **L0–L3 四级 × 配置冻结 × 时间预算合成**的闭环。
> 完整背景诊断见对话记录；本文件是落地清单。

## 设计目标（用户四要求）

1. **简洁可复现**：每次 run 冻结配置 + 数据集版本 + seed + 模型版本。
2. **全面客观**：8 维度名副其实；主观维度用双裁判+一致率；方差可测。
3. **测试分级**：L0–L3 四级，时间预算×样本量×维度覆盖明确。
4. **按时间灵活组合**：composer 按 `--time-budget` + `--dimensions` 动态产 plan。

## 现状诊断（已对照源码核实）

| 诊断 | 证据 | 影响 |
|---|---|---|
| 维度名不副实 | `metrics.py:69-102` 6 个指标 `NotImplementedError`，仅 `pass_at_1`/`function_call_accuracy` 被 executors 绕过 | IFEval/MT-Bench/TruthfulQA/SWE-bench/GAIA 跑了却报"0 分"而非"未实现" |
| AIME `n:4` 死代码 | `runner._run_one` 调 `generate()`，`_openai_generate` 取 `choices[0]` | 烧 4× token，pass@k/self-consistency 完全没生效 |
| 数据集版本破口 | `datasets.yaml` 21/24 条 `version: latest` | 同 plan 跨次跑可能对应不同数据集快照 |
| run 未冻结配置 | `runner.py:62-66` 只写 samples+summary，未拷 configs | 改 yaml 后无法复现历史 run |
| 缺 seed | params 无 seed，`_openai_generate` body 无 seed | temp>0 任务每次漂移，方差无法归因 |
| 维度↔任务硬编码 | `cli.py:11-20 SUITE_TASK_DIR` | 新增维度要改核心，违背"配置驱动" |

## P0（无外部依赖，立得住分级）— 本轮交付

| # | 功能点 | 设计文档 | 关键改动 |
|---|---|---|---|
| P0-1 | AIME 多采样 maj@1/pass@k | `docs/design/multi_sample.md` | `runner._run_one` 识别 `n>1` 调 `generate_n`；`metrics` 加 `maj@1`；bench 加 `aggregator` 字段 |
| P0-2 | 失败即响（errored≠0 分） | `docs/design/reproducibility.md` | `runner` 捕获 `NotImplementedError` 标 `errored:True`；reporter 综合得分分母剔除 errored/skipped |
| P0-3 | run 配置冻结 + seed 贯通 | `docs/design/reproducibility.md` | `run_dir/config_snapshot.yaml` 落 plan+models+datasets+benchmarks+git_hash；plan 顶层 `seed` → `_openai_generate` body.seed |
| P0-4 | L0–L3 分级 plan | `docs/design/tiers.md` | `plans/L0..L3/plan.yaml`；`methodology.md` 加分级矩阵；L0 仅 mock/内置；L1 8 维各 1 代表 |
| P0-5 | IFEval 执行器 | `docs/design/ifeval.md` | `executors.run_ifeval` + `ifeval_checker`（strict/loose 两档）；builtin mini-IFEval 样本供离线验证 |

验收（P0 收尾）：`python scripts/run_benchmark.py run --plan plans/L0/plan.yaml --model mock` 端到端跑通，`results/*/config_snapshot.yaml` 存在且含 seed/git_hash，AIME mock 多采样路径被走到，IFEval 在 builtin 样本上产出非零分，全量 `_runner.py` 绿。

## P1（让"全面客观"到位，3–5 天）

- TruthfulQA MC1/MC2 + `models.py:return_logprobs` 开关
- MT-Bench 双裁判（gpt-4o + glm-local 互判）+ 一致率
- `pass@k` 无偏估计：HumanEval/MBPP `n=5` 用 `generate_n`
- AIME self-consistency 完整：`maj@1` + `pass@k` 双报
- `datasets.yaml` version 全部回填 commit hash；`scripts/download_datasets.py` 打印 hash
- `composer.py` + `compose` 子命令；`datasets.yaml` 补 `cost_per_sample_sec`
- `cli.py SUITE_TASK_DIR` 改从 `suites/<dim>/definition.yaml.benchmarks` 动态读（配置驱动）
- `n_repeats` 整 run 复测 + `gen_summary_report` 方差段强制触发

## P2（按需，重投入）

- SWE-bench docker 执行器落地
- GAIA agent_loop 执行器落地
- HarmBench（safety 维度补充）
- 多语言：xcopa / 多语言 MMLU subset
- L3 deep plan 完整化（含 SWE/GAIA/MT-Bench）
- 跨模型对比表加"同 plan+version+seed"校验列，不符标 ⚠

## 执行节奏

每个功能点严格走 **设计文档 → 单测 → 实现 → 功能验证 → 全量回归 → 提交推送**。
单测在无 pytest 环境下用 `python tests/_runner.py` 跑；有 pytest 则 `make test`。
提交粒度：一个功能点一个 commit，commit message 中文描述+英文 type 前缀。

## 文件落点约定

- 设计文档：`docs/design/<feature>.md`
- 单测：`tests/test_<feature>.py`（含 `if __name__=="__main__"` 块）
- 实现：尽量扩展现有 `src/llm_iq_bench/*.py`，不过度新建文件
- 分级 plan：`plans/L<tier>/plan.yaml`
