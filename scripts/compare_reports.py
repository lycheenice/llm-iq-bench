#!/usr/bin/env python3
"""扫描 reports/runs/*.json，生成跨 run 对比表 reports/comparison.md。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_iq_bench.reporter import build_comparison, COMPARISON_PATH


def main():
    md = build_comparison()
    print(f"对比报告已生成: {COMPARISON_PATH.relative_to(Path.cwd()) if Path.cwd() in COMPARISON_PATH.parents else COMPARISON_PATH}")
    print("\n" + md)


if __name__ == "__main__":
    main()
