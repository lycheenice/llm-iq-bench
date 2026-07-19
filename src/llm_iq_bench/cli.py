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


def cmd_compose(args):
    from .composer import compose_plan, write_plan
    plan = compose_plan(
        dimensions=args.dimensions.split(",") if args.dimensions else [],
        time_budget_min=args.time_budget,
        model=args.model,
        seed=args.seed,
        tier=args.tier,
        max_n=args.max_n,
        include_hf=args.include_hf,
        name=args.name,
    )
    path = write_plan(plan, out_dir=args.out)
    print(f"composed plan: {path}")
    print(f"  tier={plan['tier']} budget={plan['time_budget_min']}min model={plan['model']}")
    print(f"  tasks ({len(plan['tasks'])}):")
    for t in plan["tasks"]:
        print(f"    {t['benchmark']:30s} n={t['n']}")
    if args.run:
        runner = Runner(model_id=args.model)
        runner.run_plan(path, max_per_task=args.max_n)


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

    p_compose = sub.add_parser("compose", help="按时间预算 + 维度动态产 plan")
    p_compose.add_argument("--time-budget", type=int, required=True, help="时间预算（分钟）")
    p_compose.add_argument("--dimensions", default="reasoning,coding",
                           help="逗号分隔维度，默认 reasoning,coding")
    p_compose.add_argument("--model", default="glm-local", help="模型 id")
    p_compose.add_argument("--seed", type=int, default=1234, help="随机种子")
    p_compose.add_argument("--tier", default="L1", choices=["L0", "L1", "L2", "L3"],
                           help="级别（决定默认 n）")
    p_compose.add_argument("--max-n", type=int, default=None, help="每任务 n 上限")
    p_compose.add_argument("--include-hf", action="store_true",
                           help="纳入 HF-only 任务（默认排除，因不可跑）")
    p_compose.add_argument("--name", default=None, help="plan 名（缺省 composed_<tier>_<budget>s）")
    p_compose.add_argument("--out", default=None, help="plan 输出目录（缺省 plans/<name>/）")
    p_compose.add_argument("--run", action="store_true", help="compose 后立即执行")
    p_compose.set_defaults(func=cmd_compose)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
