"""composer：按时间预算 + 维度组合动态产 plan。

`compose --time-budget 60 --dimensions reasoning,coding --model glm-local`
→ 生成 `plans/composed_<ts>/plan.yaml`，所选 benchmark 在时间预算内尽量覆盖。

策略：
- 每 dim 从 `suites/<dim>/definition.yaml.benchmarks` 取候选
- 跳过 source=huggingface 任务（不可跑，composer 默认只产可跑 plan，--include-hf 才纳入）
- 每 benchmark 取 cost_per_sample_sec 估时间，按 tier 默认 n 缩放
- budget 内贪心装满：按 dim 平摊预算，逐 task 装到 n_default 上限
- 高 variance 任务（reasoning_aime/aggregator）固定 n=4 多采样

公式：task_time = n * cost_per_sample_sec * (n_samples if multisample else 1)
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _safe_load(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_benchmarks_cfg() -> dict:
    return _safe_load(ROOT / "configs" / "benchmarks.yaml").get("benchmarks", {})


def _load_datasets_cfg() -> dict:
    return _safe_load(ROOT / "configs" / "datasets.yaml").get("datasets", {})


def _load_suite_benchmarks(dim: str) -> list[str]:
    suite = _safe_load(ROOT / "suites" / dim / "definition.yaml")
    return list(suite.get("benchmarks", []))


def _is_runnable(bench_id: str, benchmarks: dict, datasets: dict, include_hf: bool) -> bool:
    """benchmark 是否当前环境可跑（数据集非 HF 或显式 include_hf）。"""
    if bench_id not in benchmarks:
        return False
    ds_id = benchmarks[bench_id].get("dataset")
    src = datasets.get(ds_id, {}).get("source")
    if src == "huggingface" and not include_hf:
        return False
    return True


def _bench_cost(bench_id: str, benchmarks: dict, datasets: dict, n: int) -> float:
    """单 task 总耗时 = n_samples × n × cost_per_sample_sec。"""
    bench = benchmarks[bench_id]
    ds_id = bench.get("dataset")
    cost = float(datasets.get(ds_id, {}).get("cost_per_sample_sec", 5.0))
    params = bench.get("params", {})
    n_samples = int(params.get("n", 1)) if params.get("n") else 1
    return n_samples * n * cost


def _tier_default_n(tier: str) -> int:
    """各级默认每任务样本数（与 docs/design/tiers.md 对齐）。"""
    return {"L0": 6, "L1": 30, "L2": 200, "L3": 500}.get(tier, 30)


def _budget_per_dim(time_budget_sec: float, dims: list[str]) -> float:
    """每维度平摊预算；向上取整避免小维度拿 0。"""
    if not dims:
        return 0.0
    return max(time_budget_sec / len(dims), 60.0)


def compose_plan(
    dimensions: Iterable[str],
    time_budget_min: int,
    model: str = "glm-local",
    seed: int = 1234,
    tier: str = "L1",
    max_n: int | None = None,
    include_hf: bool = False,
    name: str | None = None,
) -> dict:
    """生成动态 plan dict。返回结构同 plan.yaml。

    Raises ValueError: 若无可跑任务 / 维度不存在。
    """
    dims = [d for d in dimensions if d]
    valid = {"knowledge", "reasoning", "coding", "instruction_following",
             "safety", "agent", "multilingual", "long_context"}
    bad = set(dims) - valid
    if bad:
        raise ValueError(f"未知维度: {bad}; 合法: {valid}")
    if not dims:
        raise ValueError("dimensions 不能为空")

    benchmarks = _load_benchmarks_cfg()
    datasets = _load_datasets_cfg()
    budget_sec = float(time_budget_min) * 60.0
    per_dim = _budget_per_dim(budget_sec, dims)
    default_n = _tier_default_n(tier)
    if max_n is not None and max_n < default_n:
        default_n = max_n

    tasks = []
    used_sec = 0.0
    for dim in dims:
        bids = _load_suite_benchmarks(dim)
        runnable = [b for b in bids if _is_runnable(b, benchmarks, datasets, include_hf)]
        if not runnable:
            continue  # 维度无可跑任务，跳过（不报错，让用户拿到能跑的子集）
        dim_used = 0.0
        for bid in runnable:
            n = default_n
            # 若超 max_n 截断
            if max_n is not None and n > max_n:
                n = max_n
            # 若超剩余 dim 预算，按比例缩 n（但 n>=5 才有意义）
            cost_full = _bench_cost(bid, benchmarks, datasets, n)
            remaining = per_dim - dim_used
            if cost_full > remaining and remaining > 0:
                # 缩 n 让 cost_fit ≤ remaining
                cost_unit = _bench_cost(bid, benchmarks, datasets, 1)
                if cost_unit > 0:
                    n = max(5, int(remaining / cost_unit))
            if n < 5:
                continue  # 太少无统计意义，跳过
            actual_cost = _bench_cost(bid, benchmarks, datasets, n)
            tasks.append({"benchmark": bid, "n": n})
            dim_used += actual_cost
            used_sec += actual_cost
            if dim_used >= per_dim:
                break

    if not tasks:
        raise ValueError(
            f"无可跑任务。dimensions={dims} include_hf={include_hf} budget={time_budget_min}min。"
            " 尝试加 --include-hf 或扩大 budget。"
        )

    plan_name = name or f"composed_{tier}_{int(budget_sec)}s"
    plan = {
        "name": plan_name,
        "tier": tier,
        "time_budget_min": time_budget_min,
        "seed": seed,
        "description": (
            f"composer 动态生成 — {tier} 级 {time_budget_min}min budget, "
            f"dimensions={','.join(dims)}, model={model}, "
            f"~{int(used_sec)}s 预估 (overlap={int(budget_sec-used_sec)}s 余量)。"
        ),
        "model": model,
        "tasks": tasks,
    }
    return plan


def write_plan(plan: dict, out_dir: Path | str | None = None) -> Path:
    """写 plan 到文件。缺省写 plans/<name>/plan.yaml。"""
    out = Path(out_dir) if out_dir else ROOT / "plans" / plan["name"]
    out.mkdir(parents=True, exist_ok=True)
    path = out / "plan.yaml"
    path.write_text(
        yaml.safe_dump(plan, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    # demo: 30 min L1 reasoning+coding
    p = compose_plan(["reasoning", "coding"], time_budget_min=30, tier="L1")
    print(write_plan(p))
