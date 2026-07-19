"""报告生成与跨 run 对比。

每次 run_plan 结束自动调用 emit_run_report，把可读 md + 结构化 json 快照
写入仓库内固定目录 reports/runs/（已 tracked），便于：
  - 同模型不同部署/量化方案对比
  - 不同模型对比

build_comparison 扫描 reports/runs/*.json，聚合出 reports/comparison.md。
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT / "reports" / "runs"
COMPARISON_PATH = ROOT / "reports" / "comparison.md"


def emit_run_report(summary: dict, run_dir: Path, tag: str | None = None) -> Path:
    """把一次 run 的 summary 落盘为 tracked 的 md + json。返回 md 路径。"""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    plan = summary.get("plan", "plan")
    model = summary.get("model", "model")
    ts = summary.get("timestamp", dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ"))
    base = f"{plan}__{model}"
    if tag:
        base += f"__{re.sub(r'[^A-Za-z0-9_.-]', '_', tag)}"
    base += f"__{ts}"

    json_path = RUNS_DIR / f"{base}.json"
    md_path = RUNS_DIR / f"{base}.md"

    snapshot = dict(summary)
    snapshot["tag"] = tag
    snapshot["run_dir"] = str(run_dir)
    json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path.write_text(_render_run_md(summary, tag, run_dir), encoding="utf-8")
    return md_path


def _scored_tasks(tasks: dict) -> list[dict]:
    """挑出真正跑分（非 skipped / 非 errored / 有 score）的任务。"""
    return [t for t in tasks.values()
            if not t.get("skipped") and not t.get("errored") and isinstance(t.get("score"), (int, float))]


def _render_run_md(summary: dict, tag: str | None, run_dir: Path) -> str:
    plan = summary.get("plan", "")
    model = summary.get("model", "")
    ts = summary.get("timestamp", "")
    tasks = summary.get("tasks", {})
    scored = _scored_tasks(tasks)
    overall = (sum(r.get("score", 0.0) for r in scored) / len(scored)) if scored else 0.0

    lines = [
        f"# 评测报告 — {model}",
        "",
        f"- 方案: `{plan}`",
        f"- 模型: `{model}`",
        f"- 标签: `{tag}`" if tag else None,
        f"- 时间: {ts}",
        f"- 原始结果: `results/{run_dir.name}/`",
        f"- 综合得分（已跑任务均分）: **{overall:.3f}**",
        "",
        "## 任务明细",
        "",
        "| 任务 | 指标 | 得分 | 样本数 | 状态 |",
        "|---|---|---|---|---|",
    ]
    for bid, r in tasks.items():
        if r.get("skipped"):
            lines.append(f"| {bid} | — | — | 0 | SKIPPED |")
        elif r.get("errored"):
            lines.append(f"| {bid} | — | — | 0 | ERRORED |")
        else:
            lines.append(f"| {bid} | {r.get('metric','—')} | {r.get('score',0.0):.3f} | {r.get('n',0)} | OK |")
    lines += ["", f"_自动生成于 {dt.datetime.now(dt.UTC).isoformat(timespec='seconds')}，由 reporter.emit_run_report 写入。_"]
    return "\n".join(l for l in lines if l is not None)


def build_comparison(out_path: Path = COMPARISON_PATH, glob_pattern: str = "*.json") -> str:
    """扫描 reports/runs/*.json，生成对比表 md。"""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    runs = []
    for p in sorted(RUNS_DIR.glob(glob_pattern)):
        try:
            runs.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    md = _render_comparison(runs)
    out_path.write_text(md, encoding="utf-8")
    return md


def _render_comparison(runs: list[dict]) -> str:
    if not runs:
        return "# 跨 Run 对比\n\n（暂无 reports/runs/*.json）\n"

    bench_ids: list[str] = []
    seen = set()
    for r in runs:
        for bid in r.get("tasks", {}):
            if bid not in seen:
                seen.add(bid); bench_ids.append(bid)

    lines = [
        "# 跨 Run 对比",
        "",
        f"共 {len(runs)} 次 run（来自 `reports/runs/*.json`，按模型→时间排序）。综合得分剔除 SKIPPED/ERRORED。",
        "",
        "## 总览",
        "",
        "| Run | 模型 | 方案 | 标签 | 时间 | 综合 |",
        "|---|---|---|---|---|---|",
    ]
    for r in sorted(runs, key=lambda x: (x.get("model",""), x.get("timestamp",""))):
        scored = _scored_tasks(r.get("tasks", {}))
        overall = (sum(t.get("score",0.0) for t in scored)/len(scored)) if scored else 0.0
        name = f"{r.get('plan','')}__{r.get('model','')}"
        if r.get("tag"): name += f"__{r['tag']}"
        lines.append(
            f"| {name} | {r.get('model','')} | {r.get('plan','')} | {r.get('tag','') or '—'} | "
            f"{r.get('timestamp','')} | {overall:.3f} |"
        )

    lines += ["", "## 各任务得分", "", "| Run | 模型 | " + " | ".join(bench_ids) + " |", "|" + "---|" * (len(bench_ids)+2)]
    for r in sorted(runs, key=lambda x: (x.get("model",""), x.get("timestamp",""))):
        name = r.get("plan","") + "__" + r.get("model","")
        if r.get("tag"): name += "__" + r["tag"]
        cells = []
        for bid in bench_ids:
            t = r.get("tasks", {}).get(bid)
            if not t or t.get("skipped"):
                cells.append("—")
            elif t.get("errored"):
                cells.append("ERR")
            else:
                cells.append(f"{t.get('score',0.0):.3f}")
        lines.append(f"| {name} | {r.get('model','')} | " + " | ".join(cells) + " |")

    lines += ["", "## 按模型聚合（同模型多次 run 取最新）", "", "| 模型 | 最新综合 | 任务数 |", "|---|---|---|"]
    by_model: dict[str, dict] = {}
    for r in runs:
        m = r.get("model","")
        if m not in by_model or r.get("timestamp","") > by_model[m].get("timestamp",""):
            by_model[m] = r
    for m, r in sorted(by_model.items()):
        scored = _scored_tasks(r.get("tasks",{}))
        overall = (sum(t.get("score",0.0) for t in scored)/len(scored)) if scored else 0.0
        lines.append(f"| {m} | {overall:.3f} | {len(scored)} |")

    lines += ["", f"_由 reporter.build_comparison 生成于 {dt.datetime.now(dt.UTC).isoformat(timespec='seconds')}。_"]
    return "\n".join(lines)


def build_variance_report(runs: list[dict], out_path: Path | None = None) -> str:
    """对同一 plan 的 N 次复测，计算每任务得分的均值/极差/标准差。

    runs: list[summary dict]，应来自同一 plan（按 plan name 过滤由调用方负责）。
    返回 md 字符串；若 out_path 给定则同时落盘。
    排除 skipped/errored 任务。
    """
    from statistics import mean, pstdev
    if not runs:
        md = "# 多轮稳定性报告\n\n（暂无 run）\n"
        if out_path:
            out_path.write_text(md, encoding="utf-8")
        return md

    plan_name = runs[0].get("plan", "?")
    model = runs[0].get("model", "?")
    seeds = [r.get("seed") for r in runs]
    timestamps = [r.get("timestamp", "") for r in runs]

    # 收集所有非 skipped/errored 任务 id
    all_bids: list[str] = []
    seen = set()
    for r in runs:
        for bid, t in r.get("tasks", {}).items():
            if bid not in seen and not t.get("skipped") and not t.get("errored"):
                seen.add(bid); all_bids.append(bid)

    lines = [
        f"# 多轮稳定性报告 — {model}",
        "",
        f"- 方案: `{plan_name}` | 模型: `{model}` | 轮数: {len(runs)}",
        f"- seeds: {seeds}",
        f"- 时间: {timestamps}",
        "",
        "## 各任务跨轮得分",
        "",
        "| 任务 | " + " | ".join(f"轮{i+1}" for i in range(len(runs))) + " | 均值 | 极差 | 标准差 | 稳定 |",
        "|" + "---|" * (len(runs) + 5),
    ]
    stable_count = 0
    total_count = 0
    for bid in all_bids:
        scores = []
        for r in runs:
            t = r.get("tasks", {}).get(bid)
            if t and not t.get("skipped") and not t.get("errored") and isinstance(t.get("score"), (int, float)):
                scores.append(float(t["score"]))
            else:
                scores.append(None)
        valid = [s for s in scores if s is not None]
        if len(valid) < 2:
            continue
        total_count += 1
        rng = max(valid) - min(valid)
        sd = pstdev(valid) if len(valid) > 1 else 0.0
        avg = mean(valid)
        stable = rng <= 0.05
        if stable:
            stable_count += 1
        cells = [f"{s:.3f}" if s is not None else "—" for s in scores]
        lines.append(f"| {bid} | " + " | ".join(cells) + f" | {avg:.3f} | {rng:.3f} | {sd:.3f} | {'✓' if stable else '✗'} |")

    overall_scores = []
    for r in runs:
        scored = _scored_tasks(r.get("tasks", {}))
        if scored:
            overall_scores.append(sum(t["score"] for t in scored) / len(scored))
    if overall_scores:
        ov_rng = max(overall_scores) - min(overall_scores)
        ov_sd = pstdev(overall_scores) if len(overall_scores) > 1 else 0.0
        ov_avg = mean(overall_scores)
        lines += ["", "## 综合得分跨轮", "",
                  "| " + " | ".join(f"轮{i+1}" for i in range(len(runs))) + " | 均值 | 极差 | 标准差 |",
                  "|" + "---|" * (len(runs) + 3)]
        lines.append("| " + " | ".join(f"{s:.3f}" for s in overall_scores) +
                     f" | {ov_avg:.3f} | {ov_rng:.3f} | {ov_sd:.3f} |")

    lines += ["", f"## 结论", "",
              f"- {stable_count}/{total_count} 任务极差 ≤ 0.05（稳定）。",
              "- temp=0 任务理论上应 0 方差；非 0 方差反映服务端非确定性或浮点累积。",
              "- temp>0 任务（如 AIME n=4）跨 seed 应有方差（预期）。",
              "",
              f"_由 reporter.build_variance_report 生成于 {dt.datetime.now(dt.UTC).isoformat(timespec='seconds')}。_"]
    md = "\n".join(lines)
    if out_path:
        out_path.write_text(md, encoding="utf-8")
    return md
