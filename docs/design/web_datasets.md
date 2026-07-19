# 设计：web 数据源类型（绕过 HF 库依赖）

> P1。当前环境无 pip/无 `datasets` 库/无 pandas/pyarrow，HF parquet 不可解析。
> 但 `requests` 可达 GitHub raw 与 hf-mirror JSONL/TSV/JSON/CSV。
> 新增 `source: web` 数据源，让 reasoning/multilingual 等维度可跑。

## 问题

`datasets.py._load_hf` 依赖 `from datasets import load_dataset`，本环境不可用。
`configs/datasets.yaml` 24 条里 21 条 `source: huggingface` 全部不可加载。
导致 knowledge/reasoning/multilingual/safety 维度本轮全部 skipped。

## 目标

1. 新增 `source: web` 加载器 `_load_web(spec)`：按 `url` + `format` 下载并解析。
2. 支持格式：`jsonl` / `json` / `csv` / `tsv`。
3. 缓存到 `datasets/<dim>/cache/<dataset_id>.<ext>`，二次跑零网络。
4. 字段映射复用现有 `spec.fields`；`web` 特有 `format`/`url`/`field_map`（可选重命名）。
5. 接入 3 个已验证可达数据集：gsm8k / mgsm_fr / bbh。
6. 向后兼容：现有 `builtin`/`huggingface`/`local` 不受影响。

## 接口

### spec 字段
```yaml
gsm8k:
  dim: reasoning
  source: web
  url: https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/test.jsonl
  format: jsonl
  version: 2023-openai-github
  license: MIT
  fields: {question: question, gold: answer}
  n_default: 500
```

### `_load_web(spec) -> list[dict]`
```python
def _load_web(spec):
    url = spec["url"]; fmt = spec.get("format","jsonl")
    cache = BUILTIN_DIR / spec["dim"] / "cache" / f"{dataset_id}.{fmt}"
    if not cache.exists(): requests.get(url) → 写 cache
    return _parse(cache, fmt, spec)
```

### `_parse(path, fmt, spec)`
- jsonl: 逐行 json.loads
- json: 整文件 json.loads；若是 list 直接用；若是 dict 且有 `examples` key 取 `examples`
- csv: `csv.DictReader`
- tsv: `csv.DictReader(delimiter="\t")`

### 字段映射
现有 `_gold_from` + `fields` 机制不变。对 `answer` 字段是 `"... <<18>>"` 的 gsm8k，
`answer_extractor: last_number` 在 runner 层处理（已有）。mgsm tsv 无表头，按列位置
`{0: question, 1: answer}` 映射 → 用 `spec.fields` 的值是 int 列号特判。

## 落地数据集

| id | dim | url | format | n_default | 说明 |
|---|---|---|---|---|---|
| gsm8k | reasoning | github openai/grade-school-math test.jsonl | jsonl | 500 | 1319 题，gold=answer 含推理过程 |
| mgsm_fr | multilingual | github google-research/url-nlp mgsm_fr.tsv | tsv | 250 | 法语 GSM8K，约 250 题 |
| bbh_navigate | reasoning | github sugunmirac/BIGH navigate.json | json | 250 | BBH navigate 子集 |

## 边界与不变量

- 缓存命中时不发网络（离线复跑可复现）。
- 下载失败抛 `RuntimeError`，runner 标 skipped（已有容错）。
- 不引入新依赖（仅 `requests` + stdlib `csv/json/gzip`）。
- `version` 用 GitHub 仓库 + 日期标识（commit hash 难拿，日期够用）。
- mgsm tsv 无表头：`fields` 值为 int 时按列号取。
- 单测用 `requests` mock 或本地 fixture 文件，不发真实网络（CI 友好）。

## 测试要点（tests/test_web_datasets.py）

1. `_parse` 四格式各一例（用 tmpfile 写 fixture，不网络）。
2. `_load_web` 缓存命中：第二次不下载（mock requests.get 计数）。
3. `_load_web` 下载失败 → RuntimeError。
4. gsm8k fixture：`fields={question:question, gold:answer}` 正确映射。
5. mgsm tsv 无表头 `fields={question:0, gold:1}` 按列号取。
6. bbh json dict 含 examples：取 .examples。
7. 现有 source=builtin/local/huggingface 不受影响（回归）。
8. （可选，需网络）真实 gsm8k 下载 1 题验证端到端。

## 验收

- `python3 tests/_runner.py` 全绿（新增 ≥7 条，回归 53 条不破）。
- 真实跑 `reasoning_gsm8k` 在 mock 下能加载（mock 不调网络，只验数据集加载）。
- 多轮全量对比 plan 含 gsm8k/mgsm/bbh 能跑通。
