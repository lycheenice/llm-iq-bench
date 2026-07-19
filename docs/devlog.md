# 开发日志 (devlog)

> 本文件用于记录仓库进展，方便后续接力。按时间倒序追加新条目。

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
