#!/usr/bin/env python3
"""生成图文并茂的综合评测报告 reports/summary_report.md。
扫描 reports/runs/*.json，挑每个 plan 的最新 run，产 SVG 图表 + md。
用法: python scripts/gen_summary_report.py [--with-variance]
  --with-variance: 若有多次同 plan 复测，追加精度误差分析段。
"""
import sys, json, glob, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from llm_iq_bench.charts import radial_chart, bars_chart, hbars_chart, needle_heatmap
from llm_iq_bench.reporter import RUNS_DIR, ROOT

OUT = ROOT / "reports" / "summary_report.md"


def load_runs():
    runs = []
    for p in sorted(RUNS_DIR.glob("*.json")):
        runs.append(json.loads(p.read_text(encoding="utf-8")))
    return runs


def latest_per_plan(runs):
    out = {}
    for r in runs:
        key = r.get("plan", "")
        if key not in out or r.get("timestamp", "") > out[key].get("timestamp", ""):
            out[key] = r
    return list(out.values())


def bench_scores(run):
    res = {}
    for bid, t in run.get("tasks", {}).items():
        if not t.get("skipped"):
            res[bid] = (t.get("score", 0.0), t.get("n", 0))
    return res


def fmt_pct(v):
    return f"{v*100:.1f}%"


def asset_rel(p: Path) -> str:
    return p.relative_to(ROOT / "reports").as_posix()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-variance", action="store_true")
    args = ap.parse_args()
    runs = load_runs()
    if not runs:
        OUT.write_text("# 评测报告\n\n（暂无 reports/runs/*.json）\n", encoding="utf-8")
        print("no runs"); return
    latest = latest_per_plan(runs)
    main_run = next((r for r in latest if r["plan"] == "local_v1"), latest[0])

    # ---- 图表 ----
    # 1) 雷达图：local_v1 四维
    lv1 = main_run["tasks"]
    axes = ["HumanEval", "MBPP", "BFCL", "Needle"]
    radial = radial_chart(
        axes,
        [("local_v1", [lv1.get("coding_humaneval", {}).get("score", 0),
                       lv1.get("coding_mbpp", {}).get("score", 0),
                       lv1.get("agent_bfcl", {}).get("score", 0),
                       lv1.get("long_needle", {}).get("score", 0)])],
        title="GLM-5.2 能力雷达 (local_v1)", fname="radial_main.svg",
    )
    # 2) temp 对比柱状图
    temp_groups = ["HumanEval", "MBPP"]
    t0 = next((r for r in latest if r["plan"] == "local_v1"), None)
    t02 = next((r for r in latest if r["plan"] == "coding_robust"), None)
    series_temp = []
    if t0:
        series_temp.append(("temp=0", [t0["tasks"].get("coding_humaneval", {}).get("score", 0),
                                        t0["tasks"].get("coding_mbpp", {}).get("score", 0)]))
    if t02:
        series_temp.append(("temp=0.2", [t02["tasks"].get("coding_humaneval_t02", {}).get("score", 0),
                                          t02["tasks"].get("coding_mbpp_t02", {}).get("score", 0)]))
    temp_chart = bars_chart(temp_groups, series_temp, title="温度对比：temp=0 vs temp=0.2",
                            fname="temp_compare.svg", value_fmt="{:.1%}")
    # 3) local_v1 单 run 水平柱
    items = []
    for bid, label in [("coding_humaneval","HumanEval"),("coding_mbpp","MBPP"),
                       ("agent_bfcl","BFCL 函数调用"),("long_needle","Needle 4-32k")]:
        t = lv1.get(bid)
        if t and not t.get("skipped"):
            items.append((label, t["score"]))
    hbars = hbars_chart(items, title="GLM-5.2 local_v1 各任务得分", fname="lv1_hbars.svg")
    # 4) needle 热力图（取 needle_stress）
    ns = next((r for r in latest if r["plan"] == "needle_stress"), None)
    needle_img = None
    needle_rows = []
    if ns:
        # 从 samples 重建（summary 只有聚合分，需读 samples.jsonl 取 length/depth）
        # 这里 summary 无网格数据，从 samples 读
        rd = ROOT / "results" / f"needle_stress_glm-local_{ns['timestamp']}"
        sf = rd / "samples.jsonl"
        if sf.exists():
            for l in sf.read_text(encoding="utf-8").splitlines():
                if l.strip():
                    d = json.loads(l)
                    needle_rows.append((d.get("length_tokens", 0), d.get("depth", 0),
                                        1.0 if d.get("verdict") else 0.0))
    if needle_rows:
        needle_img = needle_heatmap(needle_rows, fname="needle_heat.svg",
                                    title="Needle 压力测试：长度 × 深度 通过率")

    # ---- md ----
    lines = [f"# GLM-5.2 评测综合报告", "",
             f"> 模型: `{main_run['model']}` (sglang @ localhost:8001, api id=`glm`, 300k context, 推理模型)  ",
             f"> 数据来源: `reports/runs/*.json`（{len(runs)} 次 run，本报告取每个 plan 最新）  ",
             f"> 生成: 自动", "",
             "## 1. 能力雷达 — local_v1（编码+函数调用+长上下文）", "",
             f"![radar]({asset_rel(radial)})", "",
             "## 2. 各任务得分（local_v1）", "",
             f"![hbars]({asset_rel(hbars)})", "",
             "| 任务 | 指标 | 得分 | 样本数 |",
             "|---|---|---|---|"]
    for bid, label in [("coding_humaneval","HumanEval (pass@1)"),("coding_mbpp","MBPP (pass@1)"),
                       ("agent_bfcl","BFCL 函数调用"),("long_needle","Needle 4-32k")]:
        t = lv1.get(bid, {})
        if t and not t.get("skipped"):
            lines.append(f"| {label} | {t.get('metric','')} | {fmt_pct(t['score'])} | {t.get('n',0)} |")
    overall = sum(t["score"] for t in lv1.values() if not t.get("skipped")) / max(1, sum(1 for t in lv1.values() if not t.get("skipped")))
    lines += ["", f"**综合得分（已跑任务均分）: {fmt_pct(overall)}**", ""]

    # 温度对比
    if len(series_temp) == 2:
        lines += ["## 3. 温度鲁棒性对比（temp=0 vs 0.2）", "",
                  f"![temp]({asset_rel(temp_chart)})", "",
                  "| 任务 | temp=0 | temp=0.2 | Δ |",
                  "|---|---|---|---|"]
        for i, lb in enumerate(["HumanEval", "MBPP"]):
            a, b = series_temp[0][1][i], series_temp[1][1][i]
            lines.append(f"| {lb} | {fmt_pct(a)} | {fmt_pct(b)} | {b-a:+.1%} |")

    # needle 压力
    if needle_img:
        lines += ["## 4. 长上下文压力测试（64k–200k Needle）", "",
                  f"![needle]({asset_rel(needle_img)})", "",
                  f"整体通过率: {fmt_pct(ns['tasks']['long_needle_stress']['score'])} (n={ns['tasks']['long_needle_stress']['n']})  ",
                  "结论：4k–32k 满分(100%)，64k+ 开始衰减，200k 仍有部分召回。", ""]

    # 精度误差（复测）
    if args.with_variance:
        lines += variance_section(runs)

    lines += ["---", "",
              "## 附：所有 run 一览", "",
              "| Plan | 时间 | 任务数 | 综合 |",
              "|---|---|---|---|"]
    for r in sorted(runs, key=lambda x: (x["plan"], x["timestamp"])):
        sc = [t for t in r.get("tasks", {}).values() if not t.get("skipped")]
        ov = sum(t["score"] for t in sc)/len(sc) if sc else 0
        lines.append(f"| {r['plan']} | {r['timestamp']} | {len(sc)} | {fmt_pct(ov)} |")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"报告已生成: {OUT.relative_to(ROOT)}")
    print(f"  图表: radial={radial.name}, hbars={hbars.name}, temp={temp_chart.name}, needle={needle_img.name if needle_img else 'N/A'}")


def variance_section(runs):
    """对同一 plan 多次复测，计算每个任务得分的误差范围。"""
    from collections import defaultdict
    by_plan = defaultdict(list)
    for r in runs:
        by_plan[r["plan"]].append(r)
    lines = ["## 5. 精度误差分析（复测稳定性）", ""]
    multi = {p: rs for p, rs in by_plan.items() if len(rs) >= 2}
    if not multi:
        lines += ["（需同一 plan 跑 ≥2 次才能计算误差；当前仅 1 次。）", ""]
        return lines
    for plan, rs in multi.items():
        lines += [f"### plan=`{plan}`（{len(rs)} 次复测）", "",
                  "| 任务 | 各次得分 | 均值 | 极差 | 标准差 |",
                  "|---|---|---|---|---|"]
        from statistics import mean, pstdev
        all_bids = set()
        for r in rs:
            all_bids |= {b for b, t in r["tasks"].items() if not t.get("skipped")}
        for bid in sorted(all_bids):
            scores = [r["tasks"][bid]["score"] for r in rs
                      if bid in r["tasks"] and not r["tasks"][bid].get("skipped")]
            if len(scores) < 2:
                continue
            rng = max(scores) - min(scores)
            sd = pstdev(scores)
            lines.append(f"| {bid} | {', '.join(fmt_pct(s) for s in scores)} | "
                         f"{fmt_pct(mean(scores))} | {rng:.1%} | {sd:.1%} |")
        lines.append("")
    return lines


if __name__ == "__main__":
    main()
