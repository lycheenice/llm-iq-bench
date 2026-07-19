from __future__ import annotations

import argparse
import sys

from .config import load_models, load_datasets, load_benchmarks, load_suite
from .runner import Runner

DIMENSIONS = ["knowledge", "reasoning", "coding", "instruction_following",
              "safety", "agent", "multilingual", "long_context"]


def cmd_list(args):
    models = load_models()
    datasets = load_datasets()
    benchmarks = load_benchmarks()
    print(f"== 模型 ({len(models)}) ==")
    for m in models:
        print(f"  {m:24s} [{models[m].get('provider')}]")
    print(f"\n== 数据集 ({len(datasets)}) ==")
    for d, s in datasets.items():
        print(f"  {d:22s} dim={s.get('dim'):14s} source={s.get('source')}")
    print(f"\n== 评测任务 ({len(benchmarks)}) ==")
    for b, s in benchmarks.items():
        print(f"  {b:24s} metric={s.get('metric'):22s} on {s.get('dataset')}")
    print("\n== 维度 suite (benchmarks 从 definition.yaml 动态读) ==")
    for dim in DIMENSIONS:
        try:
            suite = load_suite(dim)
        except FileNotFoundError:
            continue
        bids = suite.get("benchmarks", [])
        print(f"  {dim}: {suite.get('title', '')}  [{len(bids)} tasks: {', '.join(bids)}]")


def cmd_run(args):
    runner = Runner(model_id=args.model)
    runner.run_plan(args.plan, max_per_task=args.n)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="llm-iq-bench", description="大模型能力评测")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="列出可用模型/数据集/任务/维度")
    p_list.set_defaults(func=cmd_list)

    p_run = sub.add_parser("run", help="执行一个测试方案")
    p_run.add_argument("--plan", required=True, help="plans/ 下的 plan.yaml 路径")
    p_run.add_argument("--model", default="mock", help="configs/models.yaml 中的模型 id")
    p_run.add_argument("--n", type=int, default=None, help="覆盖每个任务的最大样本数")
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
