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

## 结果解读

- 维度得分 = 该维度下各数据集得分的**等权平均**（可在 plan 中改为加权）。
- 跨模型对比时仅比较**同一 plan + 同一数据集版本**的结果。
- 报告中标注样本数 `n`：快速方案 `n<=200` 仅用于排序参考，全量方案才用于正式结论。
