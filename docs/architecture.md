# 架构设计

## 设计原则

1. **配置驱动**：模型、数据集、评测任务、方案全部用 YAML 描述，代码只做"加载 → 跑 → 打分 → 落盘"。
2. **维度解耦**：每个能力维度一个 `suite`，互不依赖，可单独跑或组合跑。
3. **Provider 无关**：模型客户端统一抽象为 `generate(prompt, **kwargs) -> str`，底层对接 OpenAI 兼容接口 / 本地推理 / mock。
4. **数据集外置**：数据集本体不入库，`datasets/<dim>/fetch.py` 负责下载与缓存，`definition.yaml` 声明版本/license/字段映射。
5. **结果可追溯**：每次运行生成独立目录，保存每题 raw I/O、采样参数、数据集版本、模型版本。

## 数据流

```
plan.yaml ─┐
configs/   ├─► Runner ─► 遍历 (suite, dataset, model) 组合
skills/    ─┘                  │
                               ▼
                    DatasetLoader ─► 样本流
                               │
                               ▼
                    ModelClient.generate()
                               │
                               ▼
                    Metric.compute(pred, gold)
                               │
                               ▼
                    results/<run>/{samples.jsonl, summary.json}
                               │
                               ▼
                    ReportGenerator ─► reports/<run>.md
```

## 核心抽象

### Suite（维度评测定义）
`suites/<dim>/definition.yaml`：声明该维度下挂哪些数据集、用哪类指标（accuracy / pass@1 / strict_format / win_rate）、prompt 模板、采样参数默认值。

### Plan（测试方案）
`plans/<name>/plan.yaml`：选择若干 suite、指定模型与采样参数覆盖、限定样本数（快速 vs 全量）。一个 plan = 一次可复现评测。

### Dataset Spec
`configs/datasets.yaml` + `datasets/<dim>/fetch.py`：数据集 id、HF 仓库、版本 commit、split、license、字段映射（answer 字段名等）。

### Model Spec
`configs/models.yaml`：模型 id、provider、base_url、上下文长度、默认采样参数、费用（可选）。

### Skill
`skills/*.md`：opencode 风格的"测试技巧"说明，指导对某维度如何设计探针、如何判分、常见坑。供人阅读，也可被 agent 评测流程引用。

## 扩展点

| 想新增… | 改动 |
|---|---|
| 一个数据集 | `configs/datasets.yaml` 加条目 + `datasets/<dim>/fetch.py` + suite definition 引用 |
| 一个维度 | 新建 `suites/<dim>/definition.yaml` + `datasets/<dim>/` |
| 一个模型 | `configs/models.yaml` 加条目 |
| 一个评测方案 | `plans/<name>/plan.yaml` |
| 一种指标 | `src/llm_iq_bench/metrics.py` 注册 |
| 一种 provider | `src/llm_iq_bench/models.py` 实现 `ModelClient` |

## 结果 schema

```json
// results/<run>/summary.json
{
  "plan": "quick",
  "model": "gpt-4o-mini",
  "timestamp": "20260718T120000Z",
  "dims": {
    "knowledge": {"mmlu": {"accuracy": 0.76, "n": 100, "version": "..."}},
    "reasoning": {"gsm8k": {"accuracy": 0.82, "n": 100}}
  }
}
```

```jsonl
// results/<run>/samples.jsonl
{"dim":"reasoning","dataset":"gsm8k","id":"...","prompt":"...","prediction":"...","gold":"42","correct":true}
```
