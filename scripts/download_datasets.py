#!/usr/bin/env python3
"""下载/缓存开源数据集。骨架阶段打印计划，实际下载走 datasets 库。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from llm_iq_bench.config import load_datasets
    from llm_iq_bench.datasets import load_dataset_samples

    parser = argparse.ArgumentParser(description="下载/校验开源数据集到 datasets/<dim>/cache/")
    parser.add_argument("--dim", default=None, help="只下载该维度")
    parser.add_argument("--dataset", default=None, help="只下载该数据集 id")
    parser.add_argument("--dry-run", action="store_true", help="仅打印计划")
    args = parser.parse_args()

    cfg = load_datasets()
    items = [(k, v) for k, v in cfg.items() if (not args.dim or v.get("dim") == args.dim)
             and (not args.dataset or k == args.dataset)]

    for did, spec in items:
        print(f"[{did}] dim={spec['dim']} source={spec['source']} repo={spec['repo']}")
        if spec["source"] == "builtin":
            print("  builtin 无需下载")
            continue
        if args.dry_run:
            print("  (dry-run) 将通过 hugingface datasets 下载")
            continue
        try:
            samples = load_dataset_samples(did, cfg, n=2)
            print(f"  OK: 取到 {len(samples)} 条样本")
        except Exception as e:
            print(f"  FAIL: {e}")


if __name__ == "__main__":
    main()
