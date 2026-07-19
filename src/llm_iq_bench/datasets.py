from __future__ import annotations

import csv
import gzip
import json
import os
import random
from pathlib import Path
from typing import Iterator

import requests

BUILTIN_DIR = Path(__file__).resolve().parents[2] / "datasets"


def load_dataset_samples(dataset_id: str, datasets_cfg: dict, n: int | None = None, seed: int = 0) -> list[dict]:
    spec = datasets_cfg[dataset_id]
    source = spec["source"]
    if source == "builtin":
        samples = _load_builtin(spec["repo"])
    elif source == "huggingface":
        samples = _load_hf(spec)
    elif source == "local":
        samples = _load_local(spec)
    elif source == "web":
        samples = _load_web(spec, dataset_id)
    else:
        raise ValueError(f"unknown source: {source}")
    if n is not None and n < len(samples):
        rng = random.Random(seed)
        samples = rng.sample(samples, n)
    # P1: 按 spec.fields 把源字段拷到标准名，确保 prompts.render 能取到 question/context/choices
    fields = spec.get("fields", {}) if spec else {}
    if fields:
        samples = [_normalize_sample(s, fields) for s in samples]
    return samples


# 标准键名（prompts.render 与 runner 期望的键）
_CANONICAL_KEYS = ("question", "choices", "gold", "context", "prompt",
                   "answer", "entry_point", "test", "instructions", "type",
                   "setup_code", "signature", "canonical_code")


def _normalize_sample(sample: dict, fields: dict) -> dict:
    """按 fields 把源字段值拷到标准键名（若标准键不存在）。

    fields: {canonical_name: source_name_or_index}。
    原键保留不删，仅补齐标准键。已有标准键不覆盖（向后兼容）。
    """
    out = dict(sample)
    for canon, src in fields.items():
        if canon in _CANONICAL_KEYS and src not in (None, ""):
            if isinstance(src, int):
                # TSV 无表头列号已在 _parse 阶段重命名，这里一般不触发
                continue
            if canon not in out and src in out:
                out[canon] = out[src]
    return out


def _load_builtin(repo: str) -> list[dict]:
    if repo == "builtin:demo_mc":
        return [
            {"question": "1+1=?", "choices": ["1", "2", "3", "4"], "answer": "B"},
            {"question": "水的化学式是？", "choices": ["H2O", "CO2", "O2", "NaCl"], "answer": "A"},
            {"question": "光速约为？", "choices": ["3e5 km/s", "3e8 m/s", "3e10 m/s", "3e2 m/s"], "answer": "B"},
            {"question": "地球有几颗天然卫星？", "choices": ["0", "1", "2", "3"], "answer": "B"},
            {"question": "Python 的创造者是？", "choices": ["Guido", "Linus", "Dennis", "James"], "answer": "A"},
            {"question": "中国最长河流是？", "choices": ["黄河", "长江", "珠江", "黑龙江"], "answer": "B"},
        ]
    if repo == "builtin:demo_qa":
        return [
            {"question": "一个农场有鸡兔共 35 只，脚共 94 只，鸡有多少只？", "answer": 23},
            {"question": "12 * 7 = ?", "answer": 84},
            {"question": "100 减去 37 等于多少？", "answer": 63},
            {"question": "一个数加 5 等于 12，这个数是多少？", "answer": 7},
            {"question": "3 的 4 次方是多少？", "answer": 81},
            {"question": "边长为 5 的正方形面积是多少？", "answer": 25},
        ]
    if repo == "builtin:ifeval_mini":
        return _ifeval_mini_samples()
    if repo == "builtin:aime_2024":
        return _aime_2024_samples()
    raise KeyError(f"unknown builtin dataset: {repo}")


def _aime_2024_samples() -> list[dict]:
    """3 道答案为 0-999 整数的数学题，结构模仿 AIME（验证多采样/self-consistency 路径用）。

    用于在 HF datasets 不可达环境下真实验证 maj@1 / pass@k 双报路径。
    难度梯度：Q0-1 简单，Q2 略难（验证 n=4 多采样下 maj@1 与 pass@k 差异）。
    """
    return [
        {"question": "A rectangle has length 12 and width 5. What is its area?", "gold": 60},
        {"question": "How many positive divisors does 60 have?", "gold": 12},
        {"question": "Find the remainder when 7^100 is divided by 100.", "gold": 1},
    ]


def _ifeval_mini_samples() -> list[dict]:
    """8 条覆盖关键指令类型的 mini-IFEval 样本（离线验证执行器管道用）。"""
    return [
        {"prompt": "Say hello in one sentence.",
         "instructions": [{"instruction_id": "length_constraint:num_sentences", "kwargs": {"num_sentences": 1}},
                          {"instruction_id": "punctuation:no_comma", "kwargs": {}}]},
        {"prompt": "List three colors as bullet points (one per line, numbered).",
         "instructions": [{"instruction_id": "detectable_format:number_bullet_lists", "kwargs": {"num_bullets": 3}}]},
        {"prompt": 'Return {"ok": true} as a JSON object.',
         "instructions": [{"instruction_id": "detectable_format:json_format", "kwargs": {}}]},
        {"prompt": "Write exactly 4 words.",
         "instructions": [{"instruction_id": "length_constraint:num_words", "kwargs": {"num_words": 4}}]},
        {"prompt": "Say something wrapped in double quotes.",
         "instructions": [{"instruction_id": "startend:quotation", "kwargs": {}}]},
        {"prompt": "Use Title Case for every word in your reply.",
         "instructions": [{"instruction_id": "case:capital_word", "kwargs": {}}]},
        {"prompt": "只用中文回答一句话。",
         "instructions": [{"instruction_id": "language:chinese_only", "kwargs": {}}]},
        {"prompt": "Introduce yourself briefly. No commas allowed.",
         "instructions": [{"instruction_id": "length_constraint:num_sentences", "kwargs": {"num_sentences": 1}},
                          {"instruction_id": "punctuation:no_comma", "kwargs": {}}]},
    ]


def _load_hf(spec: dict) -> list[dict]:
    try:
        from datasets import load_dataset as hf_load
    except ImportError as e:
        raise RuntimeError("需要安装 `datasets`：pip install datasets") from e
    name = spec.get("name")
    ds = hf_load(spec["repo"], name) if name else hf_load(spec["repo"])
    split = spec.get("split", "test")
    if split in ds:
        ds = ds[split]
    return [dict(row) for row in ds]


def _load_local(spec: dict) -> list[dict]:
    repo = spec["repo"]
    path = Path(repo) if os.path.isabs(repo) else BUILTIN_DIR.parent.parent / repo
    if path.suffix == ".jsonl":
        return _read_jsonl(path)
    if path.suffix == ".gz":
        return _read_jsonl(path)
    if path.suffix == ".json":
        return _read_json(path)
    if path.suffix == ".py":
        raise RuntimeError(f"本地生成器需手动实现: {path}")
    raise ValueError(f"unsupported local file: {path}")


def _read_jsonl(path: Path) -> list[dict]:
    out = []
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _read_json(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else [data]


# ============================ web 数据源（P1） ============================
# 无 HF datasets 库时，直接 requests 拉 GitHub raw / hf-mirror 的 JSONL/CSV/TSV/JSON。
# 缓存到 datasets/<dim>/cache/<id>.<ext>，二次跑零网络。

def _load_web(spec: dict, dataset_id: str) -> list[dict]:
    url = spec["url"]
    fmt = spec.get("format", "jsonl")
    dim = spec.get("dim", "_misc")
    cache_dir = BUILTIN_DIR / dim / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    ext = "jsonl.gz" if url.endswith(".gz") else fmt
    cache = cache_dir / f"{dataset_id}.{ext}"
    if not cache.exists():
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"web 数据集下载失败 {url}: {type(e).__name__}: {e}")
        cache.write_bytes(resp.content)
    return _parse(cache, fmt, spec)


def _parse(path: Path, fmt: str, spec: dict) -> list[dict]:
    """按格式解析缓存文件为 list[dict]。fields 值为 int 时按列号取（无表头 TSV）。"""
    fields = spec.get("fields", {}) if spec else {}
    opener = gzip.open if str(path).endswith(".gz") else open
    if fmt == "jsonl":
        out = []
        with opener(path, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out
    if fmt == "json":
        with opener(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = data.get("examples") or data.get("data") or data.get("items") or [data]
        return [dict(r) for r in data]
    if fmt in ("csv", "tsv"):
        delim = "\t" if fmt == "tsv" else ","
        out = []
        with opener(path, "rt", encoding="utf-8", newline="") as f:
            # fields 值有 int → 无表头，按列号取并按 fields 的 key 重命名
            int_fields = {k: v for k, v in fields.items() if isinstance(v, int)}
            has_header = not int_fields
            if has_header:
                reader = csv.DictReader(f, delimiter=delim)
                for row in reader:
                    out.append(dict(row))
            else:
                reader = csv.reader(f, delimiter=delim)
                for row in reader:
                    rec = {name: row[idx] if idx < len(row) else "" for name, idx in int_fields.items()}
                    out.append(rec)
        return out
    raise ValueError(f"unknown web format: {fmt}")
