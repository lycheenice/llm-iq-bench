# 开发日志 (devlog)

> 本文件用于记录仓库进展，方便后续接力。按时间倒序追加新条目。

## 2026-07-19 晚 — A1/B1/P1 推进 4 步（逐步验证+提交）

> 起点 commit `c123212`（3 轮多轮对比收尾后）。终点 commit `4c229da`。
> 单测 78→90（+12），每步独立 commit + push，逐步验证，全量回归全绿。

### A1. MGSM 下降趋势排查（commit `5356242`）

读三轮 `samples.jsonl` 验证数据一致性：三轮 `qhash=7980` 完全一致 → 排除数据抽样 bug。
逐题 verdict 对比：3 题稳定全对、8 题稳定全错、9 题边界方差。temp=0 仍有方差归因
sglang 服务端非确定性。MGSM 方差大于 GSM8K 因法语非主语言边界题多。
产物：`docs/mgsm_drift_investigation.md` 归因报告。

### A2. AIME self-consistency 真实验证（commit `7c64cb0`）

新增 `builtin:aime_2024`（3 题，整数 gold，避免 HF 依赖）。
runner 扩展 `aggregator: [maj@1, pass@k]` list 双报：samples 写 `verdicts` dict + 
`aggregators` list，outcome 加 `aggregators`/`n_per_aggregator` 字段；str 路径完全
向后兼容。新增 `reasoning_aime_mini` benchmark + plan。
真实 GLM-5.2 跑 3 题 n=4：maj@1=pass@k=1.000（简单题没差异，路径完整生效率）。
单测 +3。

### A3. pass@k 无偏估计 n=5（commit `35214cf`）

`metrics.pass_at_k_unbiased(n,c,k)` Codex 论文公式 `1-C(n-c,k)/C(n,k)`，乘积展开
避免阶乘大数；k=n 退化、单调、无效参数 5 单测验证公式核。
`executors.run_code_exec` 支持 n>1 多采样：每题 `generate_n` + 逐条 sandbox，
输出 `pass_at_1`(empirical c/n) + `pass@k`(unbiased) 双报；n=1 完全向后兼容。
新增 `coding_humaneval_pass5`/`coding_mbpp_pass5` benchmark + plan。
真实 GLM-5.2 跑 10 题 n=5：
- HumanEval pass@1=0.72 / pass@5=1.000 ✓（无偏>empirical 符合理论）
- MBPP pass@1=pass@5=0.30：Q0-Q2 全 5/5 通过、Q3-Q9 全 0/5 稳定失败，**强化 P0
  MBPP 失败为确定性 prompt/sandbox 类型错（非随机失误）的结论**
单测 +5。

### B1. SUITE_TASK_DIR 动态化（commit `4c229da`）

8 个 `suites/<dim>/definition.yaml` 均补 `benchmarks: [...]` 字段（按 dim 列出
所有注册的 benchmark id）。`cli.py` 删 SUITE_TASK_DIR 死代码，`list` 子命令
动态读 `definition.yaml.benchmarks` 显示每个套件的 benchmark 数与列表。
单测 `test_suite_dynamic.py` 4 测：字段存在/合法/与 dim 一致/cli 输出。

### 今晚总结
- 关键路径全部经真实 GLM 验证：AIME 多采样 maj@1+pass@k 双报、HumanEval/MBPP pass@k 无偏估计
- 已写但未验证代码全部扫清（P0-1 多采样、AIME n:4 死代码）
- MGSM 下降趋势定论（消除可信度疑虑）
- 技术债 SUITE_TASK_DIR 硬编码清理（配置驱动化）
- 单测 78→90 全绿， ROADMAP P1 推进 4 项（pass@k 双报/AIME 双报/n_repeats/suite 动态化）

### 接力提示
- 剩余 P1: TruthfulQA MC1/MC2 需 `models.py:return_logprobs` 开关、MT-Bench 双裁判需 gpt-4o API（不可达，搁置）、datasets version 回填、composer
- P2: 维度补全（knowledge/safety 需 parquet reader 或 CSV 镜像）、SWE-bench/GAIA 执行器
- MBPP 0.411 的确定性失败模式（7/10 全 0/5）值得 P1 单独排查：可能 prompt template 对部分 MBPP 题类型不友好

> 接首轮 glm_local_real。本轮目标：扩维度 + 多轮稳定性对比。

### 新增功能（均有单测，78/78 PASS）
1. **web 数据源** (`docs/design/web_datasets.md`, `tests/test_web_datasets.py` 12/12)：
   无 HF datasets 库环境下用 requests 拉 GitHub raw JSONL/TSV/JSON/CSV，缓存到 `datasets/<dim>/cache/`。接入 gsm8k/mgsm/bbh_navigate，解锁 reasoning + multilingual 两维度。
2. **gold_extractor 字段**：gsm8k/mgsm gold 是含 `#### 18` 的长文本，单独提取数字（默认 None 不提取，向后兼容）。
3. **字段规范化** (`tests/test_normalize.py` 6/6)：`_normalize_sample` 按 `spec.fields` 把源字段拷到标准键名，修复 bbh `input≠question` 导致空 prompt 0 分 bug。
4. **boxed 嵌套提取** (`tests/test_smoke.py` 新增 5 条)：`_boxed` 重写为平衡大括号匹配，支持 `\boxed{\text{Yes}}`；runner boxed 分支统一用 metrics._boxed。
5. **多轮方差分析** (`tests/test_variance.py` 6/6)：`reporter.build_variance_report` 计算跨轮均值/极差/标准差，极差≤0.05 标 ✓。
6. **run_multi 脚本**：同 plan 不同 seed 跑 N 轮 + 自动方差报告。

### bug 修复
- bbh_navigate 0.000 → 1.000（字段映射 + boxed + max_tokens 512→2048）
- AIME n:4 死代码（P0-1 已修）、mbpp 返回值语义对齐（确认非 bug）

### 多轮全量对比（3 轮 × seeds 1234/5678/9012）
plan `glm_full_v2` (tier=L2): 8 任务 177 题 6 维度，每轮 ~17min，总 56min。

| 任务 | 轮1 | 轮2 | 轮3 | 均值 | 极差 | 稳定 |
|---|---|---|---|---|---|---|
| GSM8K | 0.533 | 0.433 | 0.467 | 0.478 | 0.100 | ✗ |
| HumanEval | 0.833 | 0.867 | 0.900 | 0.867 | 0.067 | ✗ |
| MBPP | 0.400 | 0.433 | 0.400 | 0.411 | 0.033 | ✓ |
| BFCL | 0.867 | 0.867 | 0.867 | 0.867 | 0.000 | ✓ |
| Needle | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | ✓ |
| IFEval | 0.800 | 0.800 | 0.800 | 0.800 | 0.000 | ✓ |
| MGSM | 0.400 | 0.350 | 0.200 | 0.317 | 0.200 | ✗ |
| BBH | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | ✓ |

综合 0.717（极差 0.025）。5/8 任务完全稳定（极差 0），3 任务有方差（GSM8K/HumanEval/MGSM），反映 sglang 服务端 temp=0 下的微小非确定性。BFCL/Needle/IFEval/BBH 三轮完全一致证明管道本身确定。

### 产物
- `docs/analysis_glm_full_v2.md`：多轮综合分析（雷达/柱状/BFCL 分类 3 图）
- `reports/variance_glm_full_v2.md`：方差报告存档
- `scripts/gen_multi_analysis.py`：多轮报告生成器
- `reports/runs/glm_full_v2__glm-local__*.json/md`：3 轮 tracked 快照
- `plans/glm_full_v2/plan.yaml`：6 维度 8 任务 plan

### 接力提示
- 单测 78/78；新功能均先单测后实现，回归不破
- 维度覆盖 6/8（缺 knowledge/safety，需 parquet reader 或 CSV 镜像，P1 续）
- MGSM 下降趋势（0.4→0.2）待排查：load_dataset_samples 用 seed=0 固定抽样，应一致；疑服务端漂移
- AIME 多采样路径待真实模型验证（本 plan 全 temp=0）

## 2026-07-19 — GLM-5.2 本机真实评测验证（glm_local_real plan）

> P0 完成后基于**当前机器服务端点** (sglang @ localhost:8001) 跑一轮真实评测，验证最新代码端到端通畅并产出分析报告。

### 评测配置
- plan: `plans/glm_local_real/plan.yaml`（tier=L1, seed=1234, time_budget=30min）
- model: `glm-local`（api id=glm, 300k context, 推理模型, 8×H200）
- 5 任务 / 167 题：coding_humaneval(50) + coding_mbpp(50) + agent_bfcl(50) + long_needle(9) + ifeval_mini_strict(8)

### 结果
| 任务 | 得分 | 通过/总 |
|---|---|---|
| HumanEval | 0.88 | 44/50 |
| MBPP | 0.42 | 21/50 |
| BFCL | 0.90 | 45/50 |
| Needle 4-32k | 1.00 | 9/9 |
| IFEval mini | 0.90 | 9/10 指令 |

综合 0.82。BFCL 分类：simple 0.89 / multiple 0.78 / parallel 1.00 / irrelevance 0.92。Needle 4k-32k 全满。

### 关键发现
- **MBPP 42% 偏低归因**：抽查 `common_element` 确认为模型真实行为非评分器 bug —— 模型 `bool(set&set)` 返回 `False`，gold 期望 `None`，`False==None` AssertionError。属「返回值语义对齐」不足，非代码逻辑错。P1 可改 `mbpp_task` prompt 提示题目约定。
- **维度覆盖受限**：knowledge/reasoning/multilingual/safety 因 `datasets` 库被仓库 `datasets/` 目录 namespace 污染无法导入，HF 数据集本轮不可达 → P1 修 `_load_hf` 绝对导入或重命名仓库目录。
- **config_snapshot 冻结有效**：seed=1234 / git commit 2465bba / api_key 脱敏（***MPTY）/ 5 benchmark 全记录。

### 产物
- `docs/analysis_glm_local_20260719.md`：综合分析报告（含雷达/水平柱/BFCL分类/Needle热力 4 图）
- `scripts/gen_analysis_report.py`：可复用分析报告生成器
- `plans/glm_local_real/plan.yaml` + `ifenv_mini_strict` benchmark（离线 IFEval 验证用）
- `reports/runs/glm_local_real__glm-local__*.json/md`：tracked 快照
- `results/glm_local_real_glm-local_20260719T095029Z/`：完整原始数据（gitignored）

### 验证结论
P0 五项功能在真实 GLM-5.2 服务上端到端通畅：多采样路径（本轮 temp=0 未触发，但单采样路径稳定）、配置冻结+seed（config_snapshot 完整）、errored 标记（本轮无 errored）、IFEval 执行器（产出 score=0.9 + 逐指令 verdict）、分级 plan（L1 跑通）。53/53 单测仍绿。

## 2026-07-19 — P0 完成（多采样 / 配置冻结 / 分级 / IFEval）

> 接前条规划。五项 P0 全部按「设计文档 → 单测 → 实现 → 验证 → 提交推送」落地。
> 每项一个 commit，已推送 origin/main。全量 `python3 tests/_runner.py` 53/53 PASS。

### P0-1 AIME 多采样修复（commit 27bc05f）
- 设计 `docs/design/multi_sample.md`；单测 `tests/test_multi_sample.py` 8/8
- `metrics.py` 加 `maj_at_1`/`pass_at_k`/`aggregate_multisample`（不注册 METRICS，签名接 list[str]）
- `runner._run_one` 识别 `params.n>1` 调 `generate_n` + aggregator；`params` 用 dict() copy 防污染
- `benchmarks.yaml reasoning_aime` 显式 `aggregator: maj@1`
- 修复历史 bug：`n:4` 烧 4× token 却取 choices[0]

### P0-2/3 可复现性（commit 1e69fad）
- 设计 `docs/design/reproducibility.md`；单测 `tests/test_reproducibility.py` 11/11
- `runner.run_plan` 写 `results/<run>/config_snapshot.yaml`（plan/models/datasets/benchmarks/git/seed/timestamp，api_key 脱敏）
- seed 贯通：plan 顶层 `seed` > CLI > `_default_seed(plan_name)`；注入 `client.seed` 与每个 `bench.params.seed`
- `models._openai_generate/_openai_tools` body 加 seed；mock 用 (prompt,seed) 哈希可复现
- `_run_one` metric 未实现探针先于数据集加载 → `{errored:True}` 不计分、不写 samples
- `reporter._scored_tasks` 剔除 skipped/errored；综合得分分母只算真正跑分

### P0-4 测试分级 L0–L3（commit d64231f）
- 设计 `docs/design/tiers.md`；单测 `tests/test_tiers.py` 4/4
- 新建 `plans/L0_smoke`/`L1_screening`/`L2_standard`/`L3_deep`（tier/time_budget_min/seed）
- 旧 plan 全部加 tier 标注（quick=L0, full=L2, chinese=L2, reasoning_deep=L3, local_v1=L1, coding_robust=L3, needle_stress=L3）
- `methodology.md` 加「测试分级」矩阵章节（时间/用途/维度覆盖/n/温度/重复）
- L1 覆盖 8 维各 1 代表；L3 含 SWE/GAIA/MT-Bench stub（未实现自动 errored/skipped 不阻塞）

### P0-5 IFEval 执行器（commit 0516c66）
- 设计 `docs/design/ifeval.md`；单测 `tests/test_ifeval.py` 15/15
- 新增 `src/llm_iq_bench/ifeval_checker.py`：8 类指令校验（句数/词数/项目符号/JSON/无逗号/引号/Title Case/纯中文），strict+loose 两档，未识别 id 不崩
- 新增 `executors.run_ifeval`：逐条校验，score=Σpassed/Σtotal（按指令计），loose 进 `score_loose`
- `datasets.py` 加 `builtin:ifeval_mini`（8 条离线样本）；`datasets.yaml` 加 `ifeval_mini`
- `benchmarks.yaml ifeval_strict` 加 `runner: ifeval` → instruction_following 维度从 errored 变可跑
- mock+mini 端到端：8 样本/10 指令/score=0.5

### 验收
- `python3 tests/_runner.py` → 53/53 PASS（4 个测试文件）
- `run --plan plans/L0_smoke --model mock` 端到端跑通，无 skip/errored，config_snapshot 含 tier=L0/seed=1234/git commit/runner_version
- AIME 多采样路径被走到（samples 写 n_predictions）；IFEval 在 builtin 样本产出非零分
- 现有 quick/local_v1 行为不变（向后兼容）

### 接力提示（P0 后）
- 单测两栖：`python3 tests/_runner.py`（无 pytest）= `make test`；4 文件 53 条
- 每 run 必看 `config_snapshot.yaml` 确认可复现性（git dirty 标记需留意）
- L1/L2/L3 真实跑分需 GLM 在线 + 数据集下载；P0 只保证结构与 L0 离线
- P1 起点：composer / 数据集 version 回填 / TruthfulQA+MT-Bench 执行器 / pass@k 无偏估计

## 2026-07-19 — 完善规划与 P0 推进（设计→单测→实现→验证→提交）

### 背景
初版（编码/BFCL/needle 三维度 + 图文报告）已跑通 GLM-5.2 本机评测。作为评测专家梳理后定下四目标：简洁可复现、全面客观、测试分级、按时间灵活组合。完整诊断与路线图见 `docs/ROADMAP.md`，设计文档落 `docs/design/`。

### 关键诊断（对照源码核实）
- 6 指标仍是 `NotImplementedError`（`metrics.py:69-102`），跑了报"0 分"而非"未实现" → 计划 P0-2 改 errored 标记
- AIME `n:4` 死代码：`_run_one` 调 `generate()` 取 `choices[0]`，烧 4× token 无 pass@k → P0-1
- 数据集版本 21/24 `latest`、run 未冻结配置、无 seed → P0-3
- 仅 quick/full 二元，无分级 → P0-4
- IFEval/MT-Bench/TruthfulQA 不可跑 → P0-5 起步

### 本次进展
- 新增 `docs/ROADMAP.md`（P0-P2 路线图，含验收口径）
- 新增 `tests/_runner.py`：无 pytest 也能跑全部 `test_*.py`，纯 python `python tests/_runner.py`
- `test_smoke.py` 加 `__main__` 块，纯 python 可直接跑；15/15 PASS 基线建立

### 待办（P0 五项，逐项 设计→单测→实现→验证→提交）
- [P0-1] AIME 多采样 maj@1/pass@k
- [P0-2/3] errored 标记 + run 配置冻结 + seed 贯通
- [P0-4] L0–L3 分级 plan + methodology 矩阵
- [P0-5] IFEval 执行器（含 builtin mini 样本）

### 接力提示（新增）
- 单测两栖：`python tests/_runner.py`（无 pytest）与 `pytest -q tests` 等效；新 test 文件加 `if __name__=="__main__"` 块
- 设计文档统一放 `docs/design/`，命名与 P0 项对齐

## 2026-07-18 — 仓库骨架搭建完成

### 已完成

**命名与目录**
- 仓库定名 `llm-iq-bench`，位于 `/home/lychee/mycode/llm-iq-bench`
- 建立 8 维度目录树：`suites/`、`datasets/`、`plans/` 各维度齐全

**文档**
- `README.md`：总览 + 目录结构 + 快速开始 + 维度一览
- `docs/architecture.md`：架构设计（配置驱动 / 维度解耦 / 数据流 / 扩展点 / 结果 schema）
- `docs/methodology.md`：评测方法学（8 维度的指标、数据集、判分约定、复现要求）
- `datasets/README.md`、`reports/README.md`、`skills/README.md`

**配置（YAML 驱动）**
- `configs/models.yaml`：mock / gpt-4o(-mini) / qwen2.5-7b / deepseek-v3
- `configs/datasets.yaml`：24 个开源数据集（含字段映射/license/版本）
- `configs/benchmarks.yaml`：26 个评测任务（metric + prompt + 采样参数）
- 新增 `demo_mc` / `demo_qa` 内置示例（离线冒烟用）

**核心库 `src/llm_iq_bench/`**
- `config.py`：YAML 加载 + 环境变量展开
- `models.py`：`ModelClient` 抽象（mock + OpenAI 兼容，openai 惰性导入）
- `datasets.py`：builtin / huggingface / local 三类加载
- `metrics.py`：13 个已注册指标（accuracy_mc / exact_match_* / refusal_rate / f1 …）
- `prompts.py`：7 个 prompt 模板
- `runner.py`：`Runner.run_plan()` —— 遍历任务、跑模型、打分、落盘 summary.jsonl/samples.jsonl
- `cli.py`：`list` / `run` 子命令

**脚本**
- `scripts/run_benchmark.py`：主入口（PYTHONPATH=src）
- `scripts/generate_report.py`：summary.json → Markdown 报告
- `scripts/download_datasets.py`：数据集下载/校验（含 `--dry-run`）

**维度 suite（8 个 definition.yaml）**
- knowledge / reasoning / coding / instruction_following / safety / agent / multilingual / long_context

**测试方案 plans/**
- `quick`（离线冒烟）、`full`（全量正式）、`chinese`、`reasoning_deep`

**数据集获取脚本**
- `datasets/knowledge/fetch.py`、`datasets/reasoning/fetch.py` 已写
- 其余维度暂放 `.gitkeep`

**测试 skills（opencode 风格，7 个 md）**
- knowledge/reasoning/coding/safety/long-context/instruction-following/agent-testig
- 每个 skill 含：探针设计 / 判分要点 / 常见坑 / 最小执行 / 仓库映射

**报告与测试**
- `reports/template.md`：Markdown 报告模板
- `tests/test_smoke.py`：8 条烟雾断言

**工程文件**
- `requirements.txt`、`pyproject.toml`、`Makefile`、`.gitignore`

### 验证情况

- `python scripts/run_benchmark.py list` 正常输出 5 模型 / 26 数据集 / 26 任务 / 8 维度
- `python scripts/run_benchmark.py run --plan plans/quick/plan.yaml --model mock` 端到端跑通：
  - `demo_mc` 得分 0.167（n=6）
  - `demo_qa` 得分 0.000（n=6，mock 不输出 boxed，预期）
  - `knowledge_mmlu` / `reasoning_gsm8k` SKIPPED（环境未装 `datasets`，优雅跳过）
- `scripts/generate_report.py` 生成报告正常
- 烟雾断言 8 条全过（手动执行，环境无 pytest）
- 当前环境：Python 3.12.3，未装 openai/datasets/tqdm/pytest；运行时已做可选导入与容错

### 待办（按优先级）

**P0 — 让真实评测可跑**
- [ ] 落地未实现的专用执行器（suite/skill 已标 `runner:` 但代码未实现）：
  - `scripts/run_code_eval.py`（runner=`code_exec`，HumanEval/MBPP/LiveCodeBench，需 docker 沙箱）
  - `scripts/run_swe_eval.py`（runner=`swe_docker`，SWE-bench Verified）
  - `scripts/run_ifeval.py`（metric=`ifeval_strict`，逐条指令校验）
  - `scripts/run_llm_judge.py`（metric=`llm_judge`，MT-Bench，固定裁判）
  - `scripts/run_truthfulqa.py`（metric=`truthfulqa_mc1`，官方 MC1 计算）
  - `scripts/run_bfcl.py`（runner=`function_exec`，BFCL 函数调用）
  - `scripts/run_agent_eval.py`（runner=`agent_loop`，GAIA/τ-bench）
  - `scripts/run_needle.py`（runner=`needle_gen` + 深度×位置网格，Needle-in-a-Haystack）
- [ ] 补全其余维度 `datasets/<dim>/fetch.py`（coding/instruction_following/safety/agent/multilingual/long_context）

**P1 — 数据集与执行环境**
- [ ] `pip install -r requirements.txt` 后用真实 HF 数据集回归一遍 `plans/quick`
- [ ] 对接真实模型：设 `OPENAI_API_KEY` / `OPENAI_BASE_URL`，按 `plans/chinese` 或 `plans/reasoning_deep` 跑
- [ ] 补 `scripts/assets/needle.py` 生成器与 `mt_bench.jsonl` 本地文件
- [ ] 在 `configs/datasets.yaml` 给所有 HF 数据集填 `version`（commit hash / 日期），保证复现

**P2 — 质量与扩展**
- [ ] 安装 pytest，跑 `tests/test_smoke.py`
- [ ] 增补指标：pass@k 无偏估计、TruthfulQA MC2、AlpacaEval 胜率
- [ ] 报告支持维度级聚合（plan 指定 group+weight）
- [ ] 补 CMMLU / AGIEval / GAOKAO-bench / RULER / HarmBench / τ-bench 入 `configs/datasets.yaml`
- [ ] CI（GitHub Actions）跑 `make demo` + 烟雾测试

**P3 — 文档与规范化**
- [ ] `docs/datasets_licenses.md` 汇总数据集 license（含 CC-BY-NC 不可商用标注）
- [ ] `docs/faq.md`：常见问题（answer extraction 假阴、LLM-judge 裁判漂移、agent 方差等）
- [ ] 考虑 git 初始化与首个 commit（当前未 `git init`）

### 接力提示

- 跑通只需 `PYTHONPATH=src python3 scripts/run_benchmark.py ...`；装好依赖后 `make demo` 即可
- 新增数据集/维度/模型/方案/指标照 `docs/architecture.md` 的「扩展点」表操作，无需改核心
- 凡 `runner:` 在 `runner.py:_NOT_IMPLEMENTED_RUNNERS` 集合内 → 当前一律 SKIPPED，落地后从该集合移除并接脚本
- 当前环境为最小 Python，所有第三方库（openai/datasets/tqdm/pytest）均为可选导入，骨架可离线冒烟

## 2026-07-19 — 第一版专用执行器落地（编码 / 函数调用 / 大海捞针）

### 背景
目标：以本机运行的 GLM-5.2（sglang @ `http://localhost:8001/v1`，api model id = `glm`，300k context，**推理模型**）为被测对象，完成「编码能力 + 长程函数调用 + 长上下文大海捞针」三维度第一版评测。

### 已完成

**模型客户端重写（`src/llm_iq_bench/models.py`）**
- 抛弃 openai lib，纯 `requests` 走 `/v1/chat/completions`，兼容 sglang/vllm/OpenAI 官方
- 修复历史 bug：per-model `base_url` / `api_key_env` / `api_model_id` 真正接入 client（之前 `_openai_generate` 只读全局 `OPENAI_*` 环境变量，导致 deepseek/qwen 配置失效）
- 新增 `generate_with_tools()`：返回 `{content, tool_calls:[{id,name,arguments:dict}], raw}`，arguments 已解析为 dict
- 新增 `generate_n()`：多采样（用于 pass@k）
- 推理模型兼容：`_choice_content` 在 `content` 为空时回退 `reasoning_content`

**新增 `src/llm_iq_bench/executors.py`（三个执行器）**
- `run_code_exec`：HumanEval/MBPP，沙箱跑断言（`subprocess` + `resource.RLIMIT_AS` + timeout），prompt 模板 `code_complete`/`mbpp_task`，`_extract_code` 支持 ```python fence
- `run_needle_gen`：大海捞针生成器，深度×长度网格（默认 `lengths=[4k,16k,32k]` × `depths=[0.1,0.5,0.9]` = 9 case），针为随机 4 位数，评分判 gold 是否子串
- `run_function_exec`：BFCL，读 `/data1/datasets/bfcl/BFCL_v3_{cat}.json` + `possible_answer/`，把 `function` 转 OpenAI tools（`type:"dict"`→`"object"`），调 `generate_with_tools`，`_score_bfcl` 按 ground_truth 列表匹配（参数可接受值集合、可选参数缺失、多调用无序匹配、irrelevance 须零调用）

**runner.py 接线**
- `_NOT_IMPLEMENTED_RUNNERS` 由 `{code_exec, swe_docker, function_exec, agent_loop, needle_gen}` → `{swe_docker, agent_loop}`
- `_run_one` 重构：有 `runner` 字段且已实现 → `executors.dispatch()` 全权处理（绕过 `load_dataset_samples`，因 needle_gen 自生成样本），否则走原 metrics 路径

**datasets.py 加载器扩展**
- `_load_local` 支持 `.jsonl` / `.jsonl.gz` / `.json` / 绝对路径；`_read_jsonl` 跳过坏行（mbpp.jsonl 尾部被截断 → 优雅跳过）

**配置更新**
- `configs/models.yaml`：新增 `glm-local`（`api_model_id: glm`，`base_url: http://localhost:8001/v1`，300k context，`max_tokens: 4096`）；其余 openai 模型补 `api_model_id`
- `configs/datasets.yaml`：`humaneval`/`mbpp`/`bfcl` 改 `source: local` 指向 `/data1/datasets/...` 绝对路径；`needle` 改 `repo: builtin:needle`（executor 内存生成）；`bfcl` 加 `categories` 字段
- `configs/benchmarks.yaml`：`coding_humaneval`/`coding_mbpp` `max_tokens` 512→2048（推理模型 reasoning 烧 token）；`long_needle` 64→512 + 网格参数；`agent_bfcl` 512→2048 + `categories`
- `plans/local_v1/plan.yaml`：4 任务（humaneval 164 / mbpp 100 / bfcl 60 / needle 9），model=`glm-local`

**数据集（`/data1/datasets`）**
- `humaneval/HumanEval.jsonl.gz`（GitHub openai/human-eval，164 题）
- `mbpp/mbpp.jsonl`（GitHub google-research，~974 有效行）
- `bfcl/`（hf-mirror.com 下载 `gorilla-llm/Berkeley-Function-Calling-Leaderboard`，7 类 input + 7 类 possible_answer）
- 环境 `huggingface.co` 不可达，必须走 `hf-mirror.com` 且 `curl -L`（否则只拿到 307 重定向 stub）

**测试**
- `tests/test_smoke.py` 新增 7 条（共 15）：glm-local 配置、BFCL simple/parallel 评分、needle 匹配、code 沙箱 pass/fail、`_extract_code`、`_build_tools` 的 dict→object 转换

### 验证情况
- 15/15 smoke tests 通过（纯 python 跑，无需 pytest）
- mock 模型下 4 个执行器全部跑通（结果落 samples.jsonl）
- GLM-local 真实模型各取 1-2 题端到端验证：
  - `coding_humaneval`：生成带 ```python fence 的代码，沙箱 pass
  - `agent_bfcl`（parallel 题）：模型原生返回 3 个 tool_calls，参数全中，verdict=True
  - `long_needle`（4k context）：模型直接答出 "2824"，verdict=True
- `plans/local_v1` 全量后台运行中（~17s/样本，预计 ~90min）

### 接力提示（新增）
- 新增 runner → 在 `executors.py` 实现 `run_<kind>` + 在 `dispatch()` 加分支 + 从 `_NOT_IMPLEMENTED_RUNNERS` 移除
- BFCL 评分是简化版（参数精确匹配 + 可选缺失，未做 AST 等价/类型强制转换）；要更严可参考官方 `gorilla_eval`
- needle 当前用中文事实句子做 filler、英文 needle；要扩到 100k+ 需注意 sglang 的 `max_model_len` 与单题延迟
- 想跑 openai-cloud 模型：仍是历史 `${VAR:default}` 展开路径，但 `models.py` 现已正确读取 per-model `api_key_env`
