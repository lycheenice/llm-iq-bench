"""P0-4 分级 plan 结构验证 + L0 端到端冒烟。

纯 python 可跑：`python3 tests/test_tiers.py`
兼容 pytest。
"""
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_iq_bench.config import load_benchmarks
from llm_iq_bench.runner import Runner

PLANS_DIR = Path(__file__).resolve().parents[1] / "plans"

EXPECTED_TIERS = {
    "L0_smoke": "L0", "L1_screening": "L1", "L2_standard": "L2", "L3_deep": "L3",
    "quick": "L0", "full": "L2", "chinese": "L2", "reasoning_deep": "L3",
    "local_v1": "L1", "coding_robust": "L3", "needle_stress": "L3",
}


def _load_plan(name):
    with open(PLANS_DIR / name / "plan.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_all_plans_have_tier_and_seed():
    for name, tier in EXPECTED_TIERS.items():
        plan = _load_plan(name)
        assert plan.get("tier") == tier, f"{name} tier 应为 {tier}，实得 {plan.get('tier')}"
        assert "seed" in plan, f"{name} 缺 seed"


def test_L0_L1_L2_L3_tasks_resolve():
    """所有 L0–L3 plan 引用的 benchmark id 在 configs/benchmarks.yaml 都存在。"""
    bench = load_benchmarks()
    for name in ("L0_smoke", "L1_screening", "L2_standard", "L3_deep"):
        plan = _load_plan(name)
        for t in plan["tasks"]:
            bid = t["benchmark"]
            assert bid in bench, f"{name} 引用未知 benchmark: {bid}"


def test_L1_covers_8_dimensions():
    """L1 应覆盖 8 个维度（8 维各 1 代表任务）。"""
    bench = load_benchmarks()
    datasets_cfg = __import__("llm_iq_bench.config", fromlist=["load_datasets"]).load_datasets()
    plan = _load_plan("L1_screening")
    dims = set()
    for t in plan["tasks"]:
        bid = t["benchmark"]
        ds = bench[bid]["dataset"]
        dims.add(datasets_cfg[ds]["dim"])
    expected = {"knowledge", "reasoning", "coding", "instruction_following",
                "safety", "agent", "multilingual", "long_context"}
    assert dims == expected, f"L1 维度覆盖不全: {dims ^ expected}"


def test_L0_smoke_runs_mock_endtoend():
    """L0 mock 端到端：无 skip/errored，demo 任务出分。"""
    r = Runner(model_id="mock")
    summary = r.run_plan(PLANS_DIR / "L0_smoke" / "plan.yaml")
    tasks = summary["tasks"]
    assert "demo_mc" in tasks and "demo_qa" in tasks
    for bid, t in tasks.items():
        assert not t.get("skipped"), f"{bid} 不应 skip: {t}"
        assert not t.get("errored"), f"{bid} 不应 errored: {t}"
        assert "score" in t, f"{bid} 应有 score"
    # config_snapshot 存在
    snap = Path(r._last_run_dir) / "config_snapshot.yaml"
    assert snap.exists()
    data = yaml.safe_load(snap.read_text(encoding="utf-8"))
    assert data["seed"] == 1234
    assert data["plan"]["tier"] == "L0"


def _main():
    import traceback
    tests = [(n, globals()[n]) for n in list(globals())
             if n.startswith("test_") and callable(globals()[n])]
    tests.sort()
    p = f = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  test_tiers::{name}")
            p += 1
        except Exception:
            print(f"  FAIL  test_tiers::{name}")
            traceback.print_exc()
            f += 1
    print(f"=== {'OK' if f == 0 else 'FAIL'}: {p} passed, {f} failed ===")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(_main())
