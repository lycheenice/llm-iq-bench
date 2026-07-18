#!/usr/bin/env python3
"""获取 knowledge 维度数据集：mmlu / mmlu_pro / c_eval / gpqa。

用法: python datasets/knowledge/fetch.py [--dataset mmlu] [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from llm_iq_bench.config import load_datasets
from llm_iq_bench.datasets import load_dataset_samples

DIMS_DATASETS = ["mmlu", "mmlu_pro", "c_eval", "gpqa"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=None, choices=DIMS_DATASETS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg = load_datasets()
    targets = [args.dataset] if args.dataset else DIMS_DATASETS
    for did in targets:
        spec = cfg[did]
        print(f"[{did}] source={spec['source']} repo={spec['repo']} license={spec.get('license')}")
        if args.dry_run or spec["source"] == "builtin":
            continue
        try:
            samples = load_dataset_samples(did, cfg, n=2)
            print(f"  OK: {len(samples)} 样本")
        except Exception as e:
            print(f"  FAIL: {e}")


if __name__ == "__main__":
    main()
