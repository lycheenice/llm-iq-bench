from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _expand_env(value: dict) -> dict:
    out = {}
    for k, v in value.items():
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            token = v[2:-1]
            name, _, default = token.partition(":")
            out[k] = os.environ.get(name, default)
        elif isinstance(v, dict):
            out[k] = _expand_env(v)
        else:
            out[k] = v
    return out


def load_config(name: str) -> dict:
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"config not found: {path}")
    data = _load_yaml(path)
    key = name.rstrip("s") if name.endswith("s") else name
    return _expand_env(data.get(list(data.keys())[0], data))


def load_models() -> dict:
    return _load_yaml(CONFIG_DIR / "models.yaml")["models"]


def load_datasets() -> dict:
    return _load_yaml(CONFIG_DIR / "datasets.yaml")["datasets"]


def load_benchmarks() -> dict:
    return _load_yaml(CONFIG_DIR / "benchmarks.yaml")["benchmarks"]


def load_suite(dim: str) -> dict:
    path = Path(__file__).resolve().parents[2] / "suites" / dim / "definition.yaml"
    if not path.exists():
        raise FileNotFoundError(f"suite not found: {path}")
    return _load_yaml(path)


def load_plan(plan_path: str | Path) -> dict:
    with open(plan_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
