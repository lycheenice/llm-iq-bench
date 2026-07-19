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

## P0（无外部依赖，立得住分级）— **已完成 2026-07-19**

五项全部按 设计→单测→实现→验证→提交 推送。全量 `python3 tests/_runner.py` 53/53 PASS。

| # | 功能点 | 设计文档 | commit |
|---|---|---|---|
| P0-1 | AIME 多采样 maj@1/pass@k | `docs/design/multi_sample.md` | `27bc05f` |
| P0-2 | 失败即响（errored≠0 分） | `docs/design/reproducibility.md` | `1e69fad` |
| P0-3 | run 配置冻结 + seed 贯通 | `docs/design/reproducibility.md` | `1e69fad` |
| P0-4 | L0–L3 分级 plan | `docs/design/tiers.md` | `d64231f` |
| P0-5 | IFEval 执行器 | `docs/design/ifeval.md` | `0516c66` |

验收（P0 收尾，已通过）：`run --plan plans/L0_smoke --model mock` 端到端跑通，`results/*/config_snapshot.yaml` 含 seed/git_hash/tier，AIME mock 多采样路径被走到，IFEval 在 builtin 样本上产出 score=0.5，全量 53/53 PASS。

## P1（让"全面客观"到位，3–5 天）— **2026-07-19 晚推进 4 项**

> 当晚新增 4 个 commit（A1→B1），起点 `c123212` → 终点 `4c229da`。单测 78→90（+12）。

- TruthfulQA MC1/MC2 + `models.py:return_logprobs` 开关
- MT-Bench 双裁判（gpt-4o + glm-local 互判）+ 一致率
- ✅ `pass@k` 无偏估计：HumanEval/MBPP `n=5` — A3 done（commit `35214cf`）
  - `metrics.pass_at_k_unbiased(n,c,k)` Codex 公式 + `run_code_exec` 多采样路径
  - 真实 GLM: HumanEval pass@1=0.72/pass@5=1.000 ✓; MBPP 0.30/0.30 印证失败为确定性
- ✅ AIME self-consistency 完整：`maj@1` + `pass@k` 双报 — A2 done（commit `7c64cb0`）
  - runner 支持 `aggregator: [maj@1, pass@k]` list 双报 + builtin:aime_2024 验证
- `datasets.yaml` version 全部回填 commit hash；`scripts/download_datasets.py` 打印 hash
- `composer.py` + `compose` 子命令；`datasets.yaml` 补 `cost_per_sample_sec`
- ✅ `cli.py SUITE_TASK_DIR` 改从 `suites/<dim>/definition.yaml.benchmarks` 动态读 — B1 done（commit `4c229da`）
- ✅ `n_repeats` 整 run 复测 + `gen_summary_report` 方差段强制触发 — 早 P1-web done（commit `80b8199`）

附带产物：
- ✅ A1 MGSM 下降趋势排查报告 `docs/mgsm_drift_investigation.md`（commit `5356242`） — 归因 sglang 服务端 temp=0 非确定性 + 法语非主语言边界题多
- ✅ builtin:aime_2024 数据集（不依赖 HF，结构模仿 AIME）

剩余 P1：TruthfulQA MC1/MC2（需 logprobs 开关）、MT-Bench 双裁判（需外部 gpt-4o API 不可达，搁置）、datasets version 回填、composer。

## 今晚执行计划（2026-07-19 晚，逐步验证+提交+推送）

> 起点 commit `c123212`（3 轮多轮对比已收尾，综合 0.717 极差 0.025）。
> 目标：扫清"已写但未验证"代码 + 排查明显疑点，让现有 6 维度数据全部可信。
> 节奏：每步独立 commit + push，每步前 78/78 单测绿，每步后回归仍 78/N 绿。

### A1. 排查 MGSM 下降趋势（最高优先，~30min）
- 现象：3 轮 MGSM 0.400→0.350→0.200 单调下降，是唯一明显趋势
- 验证点：①`load_dataset_samples` seed=0 固定抽样是否三轮真的数据一致；②三轮 `samples.jsonl` 的 gold/id/order 对比；③若数据一致 → 服务端漂移；若不一致 → 抽样 bug
- 产物：`docs/mgsm_drift_investigation.md` 归因报告
- 提交点：归因报告 + 必要的修复

### A2. AIME self-consistency 真实验证（~1h）
- 现状：P0-1 的 `maj@1`/`pass@k` 多采样代码已写但 `glm_full_v2` 全 temp=0 没触发
- 做法：新增 `plans/aime_selfconsistency/plan.yaml`（4 题，`temperature: 0.7, n: 4`），跑 GLM 真实验证
- 验证点：`summary.json` 同时含 `maj_at_1` 和 `pass_at_k` 字段且数值合理
- 提交点：plan + 真实 run 结果 + 必要的 bug 修复

### A3. pass@k 无偏估计 n=5（~2h）
- 现状：HumanEval/MBPP 现在 n=1，pass@1=0.867/0.411
- 做法：HumanEval+MBPP 改 `n: 5, temperature: 0.7`，runner 输出 `maj@1`/`pass@5` 双报
- 验证点：跑 GLM 真实，pass@5 ≥ pass@1，maj@1 与历史 pass@1 接近
- 提交点：config 改动 + 真实 run + 报告段更新

### B1. SUITE_TASK_DIR 动态化（技术债清理，~1.5h）
- 现状：`cli.py:SUITE_TASK_DIR` 硬编码维度→目录映射，违背"配置驱动"
- 做法：改从 `suites/<dim>/definition.yaml.benchmarks` 动态读
- 验证点：新增单测 `test_suite_dynamic.py`，`list` 子命令行为不变
- 提交点：实现 + 单测

### 收尾
- 更新 `docs/devlog.md` 记录今晚进展
- 全量回归 80+/N 单测绿 — 实际 90/90 PASS（+12 新测）
- 全部 push 到 origin/main — 6 commits (`0766559`→`5356242`→`7c64cb0`→`35214cf`→`4c229da`)

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
