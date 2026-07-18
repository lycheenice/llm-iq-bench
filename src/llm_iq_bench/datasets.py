from __future__ import annotations

import gzip
import json
import os
import random
from pathlib import Path
from typing import Iterator

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
    else:
        raise ValueError(f"unknown source: {source}")
    if n is not None and n < len(samples):
        rng = random.Random(seed)
        samples = rng.sample(samples, n)
    return samples


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
    raise KeyError(f"unknown builtin dataset: {repo}")


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
