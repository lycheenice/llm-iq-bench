# datasets/ — 开源数据集获取

本目录**不放数据集本体**，只放获取脚本与缓存。实际数据下载到各维度的 `cache/` 子目录（已 gitignore）。

## 数据集来源

所有数据集在 `configs/datasets.yaml` 中登记：`source` 字段决定加载方式：

| source | 加载方式 | 缓存位置 |
|---|---|---|
| `builtin` | 仓库内置微型示例（仅供骨架冒烟） | 内存 |
| `huggingface` | `datasets.load_dataset(repo, name)` | HF 默认缓存 |
| `local` | `scripts/assets/` 下的 jsonl/py | 该文件本身 |

## 用法

```bash
# 下载/校验全部
python scripts/download_datasets.py

# 仅某维度
python scripts/download_datasets.py --dim reasoning

# 仅某数据集
python scripts/download_datasets.py --dataset gsm8k --dry-run
```

或用各维度的 `fetch.py`：

```bash
python datasets/reasoning/fetch.py
```

## 维度目录

```
datasets/
├── knowledge/         # MMLU, MMLU-Pro, C-Eval, CMMLU, AGIEval, GPQA
├── reasoning/         # GSM8K, MATH, AIME, BBH, ARC, DROP
├── coding/            # HumanEval, MBPP, LiveCodeBench, SWE-bench
├── instruction_following/  # IFEval, MT-Bench
├── safety/            # TruthfulQA, AdvBench, HarmBench, BBQ, XSTest
├── agent/             # BFCL, GAIA, τ-bench, AgentBench
├── multilingual/      # MGSM, MultiNLI, xcopa
└── long_context/      # LongBench, RULER, Needle-in-a-Haystack
```

## License

各数据集保留各自 license（见 `configs/datasets.yaml` 的 `license` 字段）。含 `CC-BY-NC` / `CC-BY-NC-SA` 的数据集**不可商用**，使用前请核对。
