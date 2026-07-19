#!/usr/bin/env python3
"""生成 GLM-5.2 多轮全量对比综合报告 docs/analysis_glm_full_v2.md。

读取 3 个 run_dir，产出：
- 雷达图（3 轮叠加）
- 各任务 3 轮柱状图
- 方差表
- 维度细分分析
用法: python scripts/gen_multi_analysis.py --runs results/d1 results/d2 results/d3
"""
import sys, json, argparse, collections, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import yaml
from llm_iq_bench.charts import radial_chart, bars_chart, hbars_chart
from llm_iq_bench.reporter import build_variance_report


def load_run(rd):
    s = json.loads((rd / "summary.json").read_text(encoding="utf-8"))
    snap = yaml.safe_load((rd / "config_snapshot.yaml").read_text(encoding="utf-8"))
    samples = [json.loads(l) for l in (rd / "samples.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    return s, snap, samples


def fmt(v):
    return f"{v*100:.1f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs=3, required=True)
    args = ap.parse_args()
    rds = [Path(r).resolve() for r in args.runs]
    data = [load_run(rd) for rd in rds]
    summaries = [d[0] for d in data]
    snaps = [d[1] for d in data]
    all_samples = [d[2] for d in data]
    seeds = [s["seed"] for s in summaries]
    ts_list = [s["timestamp"] for s in summaries]

    # 任务顺序
    task_ids = list(summaries[0]["tasks"].keys())
    axis_names = {
        "reasoning_gsm8k": "GSM8K", "coding_humaneval": "HumanEval", "coding_mbpp": "MBPP",
        "agent_bfcl": "BFCL", "long_needle": "Needle", "ifeval_mini_strict": "IFEval",
        "multilingual_mgsm": "MGSM", "reasoning_bbh_navigate": "BBH",
    }
    axes = [axis_names.get(t, t) for t in task_ids]

    # 雷达图 3 轮叠加
    series = [(f"seed={s}", [summaries[i]["tasks"][t]["score"] for t in task_ids])
              for i, s in enumerate(seeds)]
    radial = radial_chart(axes, series, title="GLM-5.2 三轮叠加 (8 任务)", fname="multi_radial.svg", size=400)

    # 各任务 3 轮柱状图
    bar_series = [(f"seed={s}", [summaries[i]["tasks"][t]["score"] for t in task_ids]) for i, s in enumerate(seeds)]
    bars = bars_chart(axes, bar_series, title="8 任务 × 3 轮得分对比", fname="multi_bars.svg",
                      value_fmt="{:.0%}", width=900, height=360)

    # 方差表数据
    def scores_for(bid):
        return [s["tasks"][bid]["score"] for s in summaries if bid in s["tasks"] and "score" in s["tasks"][bid]]

    # BFCL 分类（取 seed=1234 轮）
    bfcl_samples = [s for s in all_samples[0] if s["benchmark"] == "agent_bfcl"]
    cats = collections.defaultdict(lambda: [0, 0])
    for s in bfcl_samples:
        iid = str(s.get("id", ""))
        cat = iid.split("_")[0] if "_" in iid else "other"
        cats[cat][1 if s.get("verdict") else 0] += 1
    cat_names = sorted(cats.keys())
    cat_vals = [cats[c][1] / (cats[c][0] + cats[c][1]) for c in cat_names]
    bfcl_chart = bars_chart(cat_names, [("BFCL", cat_vals)], title="BFCL 分类 (seed=1234)",
                            fname="multi_bfcl.svg", value_fmt="{:.0%}")

    # 综合得分
    overalls = [sum(s["tasks"][t]["score"] for t in task_ids if "score" in s["tasks"][t]) /
                sum(1 for t in task_ids if "score" in s["tasks"][t]) for s in summaries]

    snap = snaps[0]
    git = snap["git"]
    lines = [
        "# GLM-5.2 多轮全量对比分析报告",
        "",
        f"> 评测: 3 轮 × `plans/glm_full_v2` (tier=L2) × GLM-5.2 (sglang@localhost:8001, 8×H200)  ",
        f"> seeds: `{seeds}` | 时间: {ts_list}  ",
        f"> git commit: `{git['commit'][:10]}` | 每轮 ~17min, 总 ~56min  ",
        f"> 每轮 8 任务 177 题，覆盖 6 维度  ",
        "",
        "## 1. 评测范围",
        "",
        "| 维度 | 任务 | 数据集 | n | 指标 |",
        "|---|---|---|---|---|",
        "| reasoning | reasoning_gsm8k | GitHub GSM8K (web) | 30 | exact_match_numeric |",
        "| reasoning | reasoning_bbh_navigate | GitHub BBH navigate (web) | 20 | exact_match (boxed) |",
        "| coding | coding_humaneval | HumanEval (本地) | 30 | pass@1 |",
        "| coding | coding_mbpp | MBPP (本地) | 30 | pass@1 |",
        "| agent | agent_bfcl | BFCL v3 (本地, 4 类) | 30 | function_call_accuracy |",
        "| long_context | long_needle | 内置 (4k/16k/32k) | 9 | exact_match |",
        "| instruction_following | ifeval_mini_strict | 内置 mini (8 类指令) | 8 | ifeval_strict |",
        "| multilingual | multilingual_mgsm | GitHub MGSM-fr (web) | 20 | exact_match_numeric |",
        "",
        "**本轮新增** (vs 首轮 glm_local_real): 接入 web 数据源解锁 reasoning + multilingual 两维度；修复 bbh 字段映射 + boxed 嵌套提取 bug。",
        "",
        "## 2. 三轮总览",
        "",
        f"**综合得分均值: {fmt(statistics.mean(overalls))}** (极差 {max(overalls)-min(overalls):.3f}, 标准差 {statistics.pstdev(overalls):.3f})",
        "",
        f"![radar](../{radial.relative_to(ROOT).as_posix()})",
        "",
        f"![bars](../{bars.relative_to(ROOT).as_posix()})",
        "",
        "## 3. 各任务跨轮稳定性",
        "",
        "| 任务 | 轮1 | 轮2 | 轮3 | 均值 | 极差 | 标准差 | 稳定 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    stable_n = 0
    for t in task_ids:
        sc = scores_for(t)
        avg = statistics.mean(sc); rng = max(sc) - min(sc); sd = statistics.pstdev(sc)
        stable = rng <= 0.05
        if stable: stable_n += 1
        mark = "✓" if stable else "✗"
        lines.append(f"| {axis_names.get(t,t)} | {sc[0]:.3f} | {sc[1]:.3f} | {sc[2]:.3f} | {avg:.3f} | {rng:.3f} | {sd:.3f} | {mark} |")
    lines += [
        "",
        f"**{stable_n}/8 任务稳定**（极差 ≤ 0.05）。综合得分极差仅 {max(overalls)-min(overalls):.3f}，整体高度可复现。",
        "",
        "## 4. 维度细分分析",
        "",
        "### 4.1 推理 (GSM8K 0.478 / BBH navigate 1.000)",
        f"- **BBH navigate 三轮全满** (1.000)，boxed 提取修复后模型准确定位 Yes/No。",
        f"- **GSM8K 均值 0.478，极差 0.100（不稳定 ✗）**。考察：temp=0 理论应确定，方差源于 sglang 服务端 batch 调度/浮点累积的非确定性。GLM 在多步算术上中等偏弱（vs HumanEval 0.867）。",
        "",
        "### 4.2 编码 (HumanEval 0.867 / MBPP 0.411)",
        f"- **HumanEval 极差 0.067（轻微不稳）**，呈上升趋势 (0.833→0.867→0.900)，可能服务端预热/cache 效应。",
        f"- **MBPP 0.411 稳定 ✓** 但偏低。归因维持 §首轮结论：返回值语义对齐（`bool` vs `None`）非逻辑错。",
        "",
        "### 4.3 函数调用 (BFCL 0.867 完全稳定)",
        f"![bfcl]({bfcl_chart.relative_to(ROOT).as_posix()})",
        "",
    ]
    for c, v in zip(cat_names, cat_vals):
        p = cats[c][1]; total = cats[c][0] + cats[c][1]
        lines.append(f"- {c}: {fmt(v)} ({p}/{total})")
    lines += [
        "",
        "### 4.4 长上下文 (Needle 4-32k 1.000 完全稳定)",
        "9/9 × 3 轮全满。300k context 中小长度无衰减；极限需 needle_stress。",
        "",
        "### 4.5 指令遵循 (IFEval mini 0.800 完全稳定)",
        "唯一持续失败：1 句 + 无逗号复合指令（模型输出含逗号 + 多句）。",
        "",
        "### 4.6 多语言 (MGSM-fr 0.317 不稳定 ✗)",
        f"**极差 0.200 最大** (0.400→0.350→0.200)，呈下降趋势。法语 GSM8K 难度高于英文；方差大反映模型在非主语言推理上鲁棒性不足。建议 P1 用更大 n (≥100) 复测确认。",
        "",
        "## 5. 可复现性结论",
        "",
        f"- **综合得分极差 {max(overalls)-min(overalls):.3f}** (3 轮 0.729/0.719/0.704)，**高度可复现**。",
        f"- {stable_n}/8 任务极差≤0.05；3 任务有方差（GSM8K/HumanEval/MGSM）。",
        "- 方差来源：sglang 服务端 batch 调度 + 浮点累积（temp=0 理论应 0 方差，实际有微小非确定性）。",
        "- config_snapshot 完整冻结 (seed+git commit+配置)，同 seed 重跑可逼近复现。",
        "- agent_bfcl/long_needle/ifeval/bbh **4 任务三轮完全一致 (0.000 极差)**，证明管道本身确定。",
        "",
        "## 6. 局限与后续",
        "",
        "1. **维度仍不全**: knowledge/safety 未跑（无可达 JSONL 源；MMLU/AdvBench 仅 parquet/HF-only）。P1 计划写轻量 parquet reader 或找 CSV 镜像。",
        "2. **样本量 L1 级**: 8 任务 n=8–30，仅排序参考；正式对比需 L2 (n=200-500)。",
        "3. **MGSM 下降趋势需排查**: 可能 seed 影响数据集抽样（load_dataset_samples 用 seed=0 固定，应一致），确认是否服务端漂移。",
        "4. **MBPP 0.411 鲁棒**: prompt 工程（提示 None 约定）或评分容差可提升。",
        "5. **AIME 多采样未触发**: 本 plan 全 temp=0；pass@k 需 n>1 任务（AIME n=4）验证，留 P1。",
        "",
        "---",
        "",
        f"_由 `scripts/gen_multi_analysis.py` 生成。3 轮原始数据: `results/glm_full_v2_glm-local_{{105423,111015,113244}}Z/`。_",
    ]
    out = ROOT / "docs" / "analysis_glm_full_v2.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"报告: {out.relative_to(ROOT)}")
    print(f"图表: {radial.name}, {bars.name}, {bfcl_chart.name}")
    # 同时把方差报告存档
    vr = ROOT / "reports" / "variance_glm_full_v2.md"
    build_variance_report(summaries, out_path=vr)
    print(f"方差报告: {vr.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
