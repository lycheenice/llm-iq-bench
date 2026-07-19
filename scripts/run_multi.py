#!/usr/bin/env python3
"""多轮评测：同一 plan 用不同 seed 跑 N 轮，结束生成方差报告。

用法:
  python scripts/run_multi.py --plan plans/glm_full_v2/plan.yaml \
    --model glm-local --rounds 3 --seeds 1234,5678,9012
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from llm_iq_bench.runner import Runner
from llm_iq_bench.reporter import RUNS_DIR, ROOT, build_variance_report

OUT = ROOT / "reports" / "variance_report.md"


def load_run_snapshot(plan, model, seed):
    """从 reports/runs/*.json 找最近一次匹配 plan+seed+model 的 summary。"""
    cands = []
    for p in RUNS_DIR.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("plan") == plan and d.get("model") == model and d.get("seed") == seed:
            cands.append(d)
    cands.sort(key=lambda x: x.get("timestamp", ""))
    return cands[-1] if cands else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--model", default="glm-local")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--seeds", default="1234,5678,9012")
    args = ap.parse_args()
    seeds = [int(s) for s in args.seeds.split(",")[:args.rounds]]
    if len(seeds) < args.rounds:
        seeds += [1234 + i for i in range(len(seeds), args.rounds)]

    plan_path = Path(args.plan).resolve()
    plan_name = plan_path.stem if plan_path.is_file() else args.plan
    print(f"=== 多轮评测: {plan_name} x {args.model} x {args.rounds} 轮 ===")
    print(f"seeds: {seeds}")

    summaries = []
    for i, seed in enumerate(seeds, 1):
        print(f"\n--- 轮 {i}/{args.rounds} seed={seed} ---")
        r = Runner(model_id=args.model, seed=seed)
        summary = r.run_plan(plan_path, seed=seed)
        summaries.append(summary)

    print("\n=== 生成方差报告 ===")
    md = build_variance_report(summaries, out_path=OUT)
    print(f"方差报告: {OUT.relative_to(ROOT)}")
    # 打印关键行
    for ln in md.splitlines():
        if "✓" in ln or "✗" in ln or "稳定" in ln or "极差" in ln and "|" in ln:
            print(" ", ln)


if __name__ == "__main__":
    main()
