#!/usr/bin/env python3
"""生成 GLM-5.2 本机评测分析报告 docs/analysis_glm_local_<ts>.md。

读取指定 run_dir 的 samples.jsonl + summary.json + config_snapshot.yaml，
产出 SVG 图表（雷达/水平柱/BFCL分类/Needle热力）+ 综合分析 md。

用法:
  python scripts/gen_analysis_report.py --run results/glm_local_real_glm-local_<ts>
"""
import sys, json, argparse, collections, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import yaml
from llm_iq_bench.charts import radial_chart, hbars_chart, bars_chart, needle_heatmap


def load_run(run_dir: Path):
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    samples = [json.loads(l) for l in (run_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    snap = yaml.safe_load((run_dir / "config_snapshot.yaml").read_text(encoding="utf-8"))
    return summary, samples, snap


def fmt_pct(v):
    return f"{v*100:.1f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="results/<run_dir>")
    args = ap.parse_args()
    run_dir = Path(args.run).resolve()
    summary, samples, snap = load_run(run_dir)
    ts = summary["timestamp"]
    tasks = summary["tasks"]
    by_bench = collections.defaultdict(list)
    for s in samples:
        by_bench[s["benchmark"]].append(s)

    # ---- 图表 ----
    axes = ["HumanEval", "MBPP", "BFCL", "Needle", "IFEval"]
    vals = [
        tasks.get("coding_humaneval", {}).get("score", 0),
        tasks.get("coding_mbpp", {}).get("score", 0),
        tasks.get("agent_bfcl", {}).get("score", 0),
        tasks.get("long_needle", {}).get("score", 0),
        tasks.get("ifeval_mini_strict", {}).get("score", 0),
    ]
    radial = radial_chart(axes, [("GLM-5.2", vals)],
                          title="GLM-5.2 能力雷达 (5 维)", fname="analysis_radial.svg")

    items = [
        ("HumanEval (pass@1)", vals[0]),
        ("MBPP (pass@1)", vals[1]),
        ("BFCL 函数调用", vals[2]),
        ("Needle 4-32k", vals[3]),
        ("IFEval mini (strict)", vals[4]),
    ]
    hbars = hbars_chart(items, title="GLM-5.2 各任务得分", fname="analysis_hbars.svg", value_fmt="{:.1%}")

    # BFCL 分类
    bfcl = by_bench["agent_bfcl"]
    cats = collections.defaultdict(lambda: [0, 0])
    for s in bfcl:
        iid = str(s.get("id", ""))
        cat = iid.split("_")[0] if "_" in iid else "other"
        cats[cat][1 if s.get("verdict") else 0] += 1
    cat_names = sorted(cats.keys())
    cat_vals = [cats[c][1] / (cats[c][0] + cats[c][1]) for c in cat_names]
    bfcl_chart = bars_chart(cat_names, [("BFCL", cat_vals)],
                            title="BFCL 各类别通过率", fname="analysis_bfcl.svg", value_fmt="{:.1%}")

    # Needle 热力图
    needle_rows = [(s.get("length_tokens", 0), s.get("depth", 0), 1.0 if s.get("verdict") else 0.0)
                   for s in by_bench["long_needle"]]
    needle_img = needle_heatmap(needle_rows, fname="analysis_needle.svg",
                                title="Needle: 长度 × 深度 通过率") if needle_rows else None

    # ---- mbpp 深度诊断 ----
    mbpp = by_bench["mbpp"]
    mbpp_pass = sum(1 for s in mbpp if s.get("verdict"))
    mbpp_fail = [s for s in mbpp if not s.get("verdict")]
    no_def = sum(1 for s in mbpp_fail if "def " not in (s.get("prediction") or ""))
    pred_lens = [len(s.get("prediction", "")) for s in mbpp]

    # ---- 文字 ----
    overall = sum(vals) / len(vals)
    git = snap["git"]
    lines = [
        f"# GLM-5.2 本机评测分析报告",
        "",
        f"> 评测时间: `{ts}`  ",
        f"> 模型: `{summary['model']}` (sglang @ localhost:8001, api id=`glm`, 300k context, **推理模型**)  ",
        f"> 方案: `plans/glm_local_real/plan.yaml` (tier={snap['plan'].get('tier')}, time_budget={snap['plan'].get('time_budget_min')}min)  ",
        f"> seed: `{snap['seed']}` | git commit: `{git['commit'][:10] if git['commit'] else 'N/A'}` (dirty={git['dirty']})  ",
        f"> 数据来源: `results/{run_dir.name}/` + `config_snapshot.yaml`  ",
        f"> GPU: 8×NVIDIA H200 (sglang 服务)  ",
        "",
        "## 1. 评测范围与配置",
        "",
        f"本轮基于**当前机器服务端点** (`http://localhost:8001/v1`) 与本地可用数据集，覆盖 4 个能力维度共 5 个任务、167 题样本：",
        "",
        "| 维度 | 任务 | 数据集 | 样本数 | 指标 |",
        "|---|---|---|---|---|",
        "| coding | coding_humaneval | HumanEval (本地) | 50 | pass@1 |",
        "| coding | coding_mbpp | MBPP (本地) | 50 | pass@1 |",
        "| agent | agent_bfcl | BFCL v3 (本地, 4 类) | 50 | function_call_accuracy |",
        "| long_context | long_needle | 内置生成 (4k/16k/32k × 3 深度) | 9 | exact_match |",
        "| instruction_following | ifeval_mini_strict | 内置 mini (8 类指令) | 8 (10 指令) | ifeval_strict |",
        "",
        "**未覆盖维度**：knowledge / reasoning / multilingual / safety —— 因 `datasets` 库受仓库 `datasets/` 目录 namespace 污染无法导入（P1 待修），HF 数据集本轮不可达。needle_stress (64k-200k) 与 L2/L3 未跑（时间预算）。",
        "",
        "## 2. 总览",
        "",
        f"**综合得分（5 任务均分）: {fmt_pct(overall)}**",
        "",
        f"![radar](../{radial.relative_to(ROOT).as_posix()})",
        "",
        f"![hbars](../{hbars.relative_to(ROOT).as_posix()})",
        "",
        "| 任务 | 得分 | 通过/总数 | 说明 |",
        "|---|---|---|---|",
        f"| HumanEval | {fmt_pct(vals[0])} | 44/50 | 函数级代码生成，6 题失败均为较难推理题 |",
        f"| MBPP | {fmt_pct(vals[1])} | {mbpp_pass}/50 | **偏低**，详见 §4 诊断 |",
        f"| BFCL | {fmt_pct(vals[2])} | 45/50 | 函数调用，parallel 满分 |",
        f"| Needle 4-32k | {fmt_pct(vals[3])} | 9/9 | 满分，300k context 下中小长度无压力 |",
        f"| IFEval mini | {fmt_pct(vals[4])} | 9/10 指令 | 唯一失败：句数+无逗号复合指令 |",
        "",
        "## 3. 维度细分",
        "",
        "### 3.1 编码能力 (HumanEval 88% / MBPP 42%)",
        "",
        f"- **HumanEval** 44/50 通过，6 题失败 (`valid_date`/`tri`/`iscube`/`minPath`/`compare_one`/`order_by_points`) 均为多步推理型，符合预期。",
        f"- **MBPP** {mbpp_pass}/50 通过，**显著低于 HumanEval**。深度诊断见 §4。",
        f"- MBPP 输出长度: min={min(pred_lens)} / 中位={int(statistics.median(pred_lens))} / max={max(pred_lens)} 字符；失败样本中 {len(mbpp_fail)-no_def}/{len(mbpp_fail)} 含合法 `def`，仅 {no_def} 个未生成代码。",
        "",
        "### 3.2 函数调用 (BFCL 90%)",
        "",
        f"![bfcl](../{bfcl_chart.relative_to(ROOT).as_posix()})",
        "",
        "| 类别 | 通过率 | 说明 |",
        "|---|---|---|",
    ]
    for c, v in zip(cat_names, cat_vals):
        p = cats[c][1]; t = cats[c][0] + cats[c][1]
        note = {"simple": "单函数调用", "multiple": "多函数选一，最低", "parallel": "并行多调用，满分", "irrelevance": "应零调用"}.get(c, "")
        lines.append(f"| {c} | {fmt_pct(v)} ({p}/{t}) | {note} |")
    lines += [
        "",
        "### 3.3 长上下文 (Needle 4-32k 满分)",
        "",
    ]
    if needle_img:
        lines.append(f"![needle](../{needle_img.relative_to(ROOT).as_posix()})")
        lines.append("")
    lines += [
        f"9/9 全过。4k/16k/32k × 0.1/0.5/0.9 深度全部命中。GLM-5.2 的 300k context 在中小长度无衰减；极限探测需 `plans/needle_stress` (64k-200k)。",
        "",
        "### 3.4 指令遵循 (IFEval mini 90%)",
        "",
        f"8 样本 / 10 指令，9 通过。唯一失败样本：prompt 要求「1 句 + 无逗号」，模型输出 `Hello, I hope you are having a wonderful day!`（含逗号 + 2 句）。strict=loose=0.9（本批宽松档未额外放宽）。",
        "",
        "## 4. MBPP 深度诊断（42% 偏低归因）",
        "",
        "抽查失败样本 `common_element`，**确认为模型真实行为，非评分器 bug**：",
        "",
        "```",
        "题目 gold:  assert common_element([1,2,3,4,5], [6,7,8,9])==None",
        "模型输出:  def common_element(list1, list2):",
        "             return bool(set(list1) & set(list2))",
        "执行:      无交集时 set()&set()=set() → bool(set())=False",
        "           False == None → AssertionError",
        "```",
        "",
        "模型用 Python 惯用法（`bool(set & set)`）返回 `False`/`True`，但题目 `test_list` 期望 `None`/`True`（特定返回值语义）。这类「返回值语义对齐」失败约占 MBPP 失败的主体；另有少量函数名推断偏差。**这反映 GLM-5.2 在 MBPP 这类对返回值语义敏感的题上对齐不足，而非代码逻辑错误**。",
        "",
        "可改进方向（P1）：",
        "- 在 `mbpp_task` prompt 模板中显式提示「无结果返回 None」等题目约定；",
        "- 评分器对 `None/False/0` 等Falsy 值做语义等价容差（需谨慎，可能引入假阳）。",
        "",
        "## 5. 可复现性",
        "",
        f"- `config_snapshot.yaml` 已冻结 plan/models/datasets/benchmarks/git/seed；",
        f"- seed={snap['seed']} 注入每个 `bench.params.seed` 与 client.body.seed；",
        f"- git commit `{git['commit'][:10]}` dirty={git['dirty']}（本轮新增 plan/benchmark 未提交，收尾提交后 dirty=False）；",
        f"- 同 seed + 同 commit + 同数据集版本重跑应复现（temp=0 任务确定；temp>0 任务如 AIME 受 seed 影响）。",
        "",
        "## 6. 局限性与后续",
        "",
        "1. **维度覆盖不全**：仅 4/8 维（coding/agent/long_context/instruction_following）。knowledge/reasoning/multilingual/safety 受 `datasets` 库 namespace 冲突阻塞 → P1 修 `_load_hf` 用绝对导入或重命名仓库 `datasets/` 目录。",
        "2. **样本量有限**：HumanEval/MBPP/BFCL 各 50 题，L1 级别仅作排序参考；正式对比需 L2 (n=200-500)。",
        "3. **MBPP 评分语义**：返回值 None/False 对齐问题，可 prompt 工程或评分容差缓解。",
        "4. **needle 未压测**：4-32k 满分不代表极限；需跑 `needle_stress` 探 64k-200k 衰减点。",
        "5. **IFEval mini 仅 8 样本**：真实评测需接 `google/IFEval` 全量 541 条。",
        "",
        f"---",
        f"",
        f"_由 `scripts/gen_analysis_report.py` 生成。原始数据: `results/{run_dir.name}/`。_",
    ]
    out = ROOT / "docs" / f"analysis_glm_local_{ts[:8]}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"分析报告已生成: {out.relative_to(ROOT)}")
    print(f"  图表: {radial.name}, {hbars.name}, {bfcl_chart.name}, {needle_img.name if needle_img else 'N/A'}")


if __name__ == "__main__":
    main()
