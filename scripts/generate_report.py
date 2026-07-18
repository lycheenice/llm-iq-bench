#!/usr/bin/env python3
"""从 results/<run>/summary.json + samples.jsonl 生成 Markdown 报告。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def main():
    parser = argparse.ArgumentParser(description="生成 Markdown 评测报告")
    parser.add_argument("--results", required=True, help="results/<run> 目录")
    parser.add_argument("--out", required=True, help="输出 .md 路径")
    args = parser.parse_args()

    run_dir = Path(args.results)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))

    lines = [
        f"# 评测报告 — {summary['model']}",
        "",
        f"- 方案: `{summary['plan']}`",
        f"- 模型: `{summary['model']}`",
        f"- 时间: {summary['timestamp']}",
        "",
        "## 总览",
        "",
        "| 任务 | 指标 | 得分 | 样本数 |",
        "|---|---|---|---|",
    ]
    for bid, r in summary["tasks"].items():
        if r.get("skipped"):
            lines.append(f"| {bid} | — | SKIPPED | 0 |")
        else:
            lines.append(f"| {bid} | {r['metric']} | {r['score']:.3f} | {r['n']} |")
    lines.append("")
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"报告已生成: {args.out}")


if __name__ == "__main__":
    main()
