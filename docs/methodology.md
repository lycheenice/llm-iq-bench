# 评测方法学

## 评测方法分类

| 方法 | 适用 | 本仓库体现 |
|---|---|---|
| 客观基准（准确率/通过率） | 知识、推理、代码、指令遵循 | suites 中多数任务 |
| LLM-as-Judge | 对话质量、开放问答 | `instruction_following` 中 MT-Bench 模式 |
| 指令遵循机械校验 | 格式约束 | IFEval（strict/loose 两档） |
| 成对胜率 | 对齐质量 | AlpacaEval 模式 |
| Agent 任务成功率 | 工具调用/多步 | `agent` 维度 |
| 长上下文探针 | 召回 | `long_context` 维度 |

## 能力维度定义

### 1. knowledge（知识广度）
- 能力：跨学科事实性知识与基础应用。
- 指标：多选题 accuracy。
- 数据集：MMLU / MMLU-Pro / C-Eval / CMMLU / AGIEval / GAOKAO-bench / GPQA。
- 注意：GPQA 为研究生级、防搜索题，用于天花板探测。

### 2. reasoning（数学与推理）
- 能力：多步算术、符号推理、竞赛数学。
- 指标：最终答案 accuracy（用 `extract_answer` 后比对，容忍 `\boxed{}` 等格式）。
- 数据集：GSM8K / MATH / AIME / AMC / OlympiadBench / BBH / ARC-Challenge / DROP。
- 注意：需统一 answer extraction，避免格式差异造成假阴性。

### 3. coding（代码能力）
- 能力：函数级生成、多语言、真实软件工程。
- 指标：pass@1（执行测试用例通过率），SWE-bench 用单元测试 resolved 率。
- 数据集：HumanEval / MBPP / LiveCodeBench / MultiPL-E / SWE-bench(-Verified)。
- 注意：需沙箱执行；SWE-bench 需 docker 环境。

### 4. instruction_following（指令遵循与对话）
- 能力：可验证格式约束、多轮连贯、对齐偏好。
- 指标：IFEval strict/loose 准确率；MT-Bench 用 GPT-4 判分（1-10）；AlpacaEval 用胜率。
- 注意：LLM-as-Judge 需固定裁判模型与 prompt，并报告裁判版本。

### 5. safety（安全与防幻觉）
- 能力：拒绝有害请求、避免常见误区、减少偏见、不过度拒绝。
- 指标：TruthfulQA 真实性；AdvBench/HarmBench 拒绝率；XSTest 过度拒绝率；BBQ 偏见分。
- 数据集：TruthfulQA / AdvBench / HarmBench / BBQ / XSTest。
- 注意：区分"安全拒绝"与"过度拒绝"两个方向，单独报。

### 6. agent（Agent / 工具调用）
- 能力：函数调用正确性、多步任务规划与执行。
- 指标：BFCL 函数调用准确率；GAIA/τ-bench 端到端任务成功率。
- 数据集：BFCL / GAIA / τ-bench / AgentBench。
- 注意：需要真实工具环境，结果方差大，建议多次取均值。

### 7. multilingual（多语言）
- 能力：非英文场景下的推理与理解。
- 指标：与对应英文基准同口径（MGSM 用 accuracy）。
- 数据集：MGSM / MultiNLI / xcopa / 多语言 MMLU。

### 8. long_context（长上下文）
- 能力：长文档内信息检索与综合。
- 指标：Needle 召回率；LongBench/RULER 综合 F1/EM。
- 数据集：Needle-in-a-Haystack / LongBench / RULER。
- 注意：需按模型上下文长度自适应调整文档规模，报告 token 数。

## 复现性要求

- 固定 `seed`，温度需为 0 的任务强制 `temperature=0`。
- 记录数据集 `version`（HF commit / 下载日期）与模型 `version`（API snapshot 或权重 hash）。
- prompt 模板随结果一并落盘。
- 每次 run 在 `results/<run>/config_snapshot.yaml` 冻结 plan+models+datasets+benchmarks+git commit+seed。

## 测试分级 (L0–L3)

按时间预算×样本量×维度覆盖分四级，plan 顶层 `tier` 字段声明。同 tier + 同 seed + 同数据集版本的结果才可跨模型直接对比。

| 级别 | 时间 | 用途 | 维度覆盖 | 每任务 n | 温度 | 重复 | 对应 plan |
|---|---|---|---|---|---|---|---|
| **L0 smoke** | <1 min | 离线冒烟/CI | knowledge+reasoning demo only | 6 | 0 | 1 | `plans/L0_smoke`（=`quick`） |
| **L1 screening** | ~20 min | 快速排序/初筛 | 8 维各 1 代表任务 | 30 | 0（AIME 0.7×4） | 1 | `plans/L1_screening` |
| **L2 standard** | ~2 h | 正式对比基准 | 8 维全量代表集 | 200–500 | 0（AIME 0.7×4） | 1 | `plans/L2_standard`（=`full`） |
| **L3 deep** | ≥8 h | 深度/天花板 | L2 + SWE-bench + GAIA + MT-Bench + 多语言全集 | 全量 n_default | 含 t=0.2 鲁棒性 | 3 | `plans/L3_deep` |

### 各级适用场景
- **L0**：验证框架可跑、CI 冒烟、回归测试。零网络零依赖。
- **L1**：拿到新模型先跑 L1 排个序，决定是否值得投入 L2。20 分钟内出结果。
- **L2**：正式横向对比的口径；论文/汇报数据用这级。所有维度代表任务，样本量足够稳定。
- **L3**：深度评估，含 SWE-bench/GAIA 等重任务，需 docker/agent 环境；多轮复测报方差。

### L1 代表任务（8 维各 1）
`knowledge_mmlu` / `reasoning_gsm8k` / `coding_humaneval` / `ifeval_strict` / `safety_advbench` / `agent_bfcl` / `multilingual_mgsm` / `long_needle`

### 灵活组合
P1 将提供 `compose` 子命令：按 `--time-budget` + `--dimensions` 动态产 plan。当前可手改 L1/L2 plan 或用 CLI `--n` 覆盖样本数。

## 结果解读

- 维度得分 = 该维度下各数据集得分的**等权平均**（可在 plan 中改为加权）。
- 跨模型对比时仅比较**同一 plan + 同一数据集版本**的结果。
- 报告中标注样本数 `n`：快速方案 `n<=200` 仅用于排序参考，全量方案才用于正式结论。
