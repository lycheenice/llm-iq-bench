# llm-iq-bench

大语言模型能力（智力）评测代码仓库。存放**测试脚本、测试方案、测试 skill**，引用**开源数据集**对模型进行多维度评测，并产出可对比的评测报告。

## 设计目标

- **维度化**：把模型能力拆成知识 / 推理 / 代码 / 指令遵循 / 安全 / Agent / 多语言 / 长上下文 8 个维度，分别可独立评测。
- **可复现**：固定数据集版本、固定 prompt、固定采样参数，结果落盘可追溯。
- **可组合**：用 `plans/` 中的方案组合不同维度与数据集，一键跑通。
- **可扩展**：新增数据集 / 维度 / 模型只需加配置，不改核心代码。
- **零密钥可跑**：内置 `mock` 模型与微型示例数据集，无 API key 即可验证骨架。

## 目录结构

```
llm-iq-bench/
├── docs/                 # 架构设计与评测方法学
│   ├── architecture.md
│   └── methodology.md
├── configs/              # 模型 / 数据集 / 评测任务配置 (YAML)
│   ├── models.yaml
│   ├── datasets.yaml
│   └── benchmarks.yaml
├── scripts/             # 命令行入口
│   ├── run_benchmark.py
│   ├── download_datasets.py
│   └── generate_report.py
├── src/llm_iq_bench/    # 核心库
│   ├── runner.py         # 评测运行器
│   ├── metrics.py        # 指标计算
│   ├── models.py         # 模型客户端（OpenAI 兼容 / mock）
│   ├── datasets.py       # 数据集加载
│   └── utils.py
├── suites/              # 各能力维度评测定义（task spec）
│   └── {knowledge,reasoning,coding,...}/definition.yaml
├── plans/               # 测试方案（维度 + 数据集 + 模型组合）
│   └── {quick,full,chinese,reasoning_deep}/plan.yaml
├── datasets/            # 开源数据集获取脚本与缓存目录
│   └── {dimension}/fetch.py
├── skills/              # opencode 风格测试 skill
│   └── *.md
├── results/             # 原始结果输出（JSONL/JSON）
├── reports/             # 汇总报告与模板
└── tests/               # 单元测试
```

## 快速开始

```bash
# 安装依赖
make install

# 验证骨架（mock 模型 + 内置示例数据，无需 API key）
make demo

# 列出可用维度 / 数据集 / 方案
python scripts/run_benchmark.py list

# 跑一个快速方案
python scripts/run_benchmark.py run --plan plans/quick/plan.yaml --model mock

# 对接真实模型（OpenAI 兼容接口）
export OPENAI_API_KEY=sk-xxx
export OPENAI_BASE_URL=https://api.openai.com/v1
python scripts/run_benchmark.py run --plan plans/quick/plan.yaml --model gpt-4o-mini

# 生成报告
python scripts/generate_report.py --results results/latest --out reports/latest.md
```

## 评测维度一览

| 维度 | 评测能力 | 代表开源数据集 |
|---|---|---|
| knowledge | 学科通识 / 知识广度 | MMLU, MMLU-Pro, C-Eval, CMMLU, AGIEval, GPQA |
| reasoning | 数学 / 逻辑 / 推理 | GSM8K, MATH, AIME, BBH, ARC, DROP |
| coding | 代码生成 / 软件工程 | HumanEval, MBPP, LiveCodeBench, SWE-bench |
| instruction_following | 指令遵循 / 对话质量 | IFEval, MT-Bench, AlpacaEval |
| safety | 安全 / 防幻觉 / 偏见 | TruthfulQA, AdvBench, BBQ, XSTest |
| agent | 工具调用 / 多步任务 | BFCL, GAIA, τ-bench, AgentBench |
| multilingual | 多语言 | MGSM, MultiNLI, xcopa |
| long_context | 长上下文召回 | Needle-in-a-Haystack, LongBench, RULER |

详见 `docs/methodology.md`。

## 约定

- 数据集**不直接入库**，仅放获取脚本与版本说明，实际数据进 `datasets/<dim>/cache/`（已 gitignore）。
- 结果按 `results/<plan>_<model>_<timestamp>/` 落盘，含每题原始输出与聚合指标。
- 评测遵循各数据集官方 license，加载时在 `definition.yaml` 中声明。

## License

仓库骨架为 MIT；引用的开源数据集保留各自 license。
