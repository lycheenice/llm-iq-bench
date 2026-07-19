"""composer 单测：动态 plan 生成。`python3 tests/test_composer.py`"""
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_iq_bench.composer import compose_plan, write_plan
from llm_iq_bench.config import load_benchmarks, load_datasets


def test_compose_basic_structure():
    p = compose_plan(["reasoning", "coding"], time_budget_min=20, tier="L1")
    assert p["tier"] == "L1"
    assert p["model"] == "glm-local"
    assert p["seed"] == 1234
    assert p["time_budget_min"] == 20
    assert isinstance(p["tasks"], list) and len(p["tasks"]) > 0
    for t in p["tasks"]:
        assert "benchmark" in t and "n" in t and t["n"] >= 5


def test_compose_only_runnable_no_hf():
    """默认不 include_hf，所有任务 source 应非 huggingface。"""
    p = compose_plan(["reasoning", "coding", "instruction_following"],
                     time_budget_min=20, tier="L1", include_hf=False)
    datasets = load_datasets()
    benchmarks = load_benchmarks()
    for t in p["tasks"]:
        ds = benchmarks[t["benchmark"]]["dataset"]
        assert datasets[ds]["source"] != "huggingface", \
            f"默认模式不应纳 HF 任务: {t['benchmark']}"


def test_compose_unknown_dim_raises():
    try:
        compose_plan(["bogus_dim"], time_budget_min=10)
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown dim")


def test_compose_empty_dims_raises():
    try:
        compose_plan([], time_budget_min=10)
    except ValueError:
        return
    raise AssertionError("expected ValueError for empty dims")


def test_compose_no_runnable_raises_when_only_hf():
    """safety 维度全部 HF-only，不 include_hf 时应 raise。"""
    try:
        compose_plan(["safety"], time_budget_min=10, include_hf=False)
    except ValueError:
        return
    raise AssertionError("safety 仅 HF-only，应 raise")


def test_compose_include_hf_enables_safety():
    """include_hf=True 时 safety 可纳入（虽实际跑会 skip，但 plan 能产）。"""
    p = compose_plan(["safety"], time_budget_min=10, include_hf=True, max_n=10)
    assert len(p["tasks"]) > 0
    assert all(t["n"] <= 10 for t in p["tasks"])


def test_compose_budget_scales_n():
    """大 budget 应给出更多 n 或更多任务（vs 小 budget）。"""
    small = compose_plan(["reasoning"], time_budget_min=5, tier="L1")
    big = compose_plan(["reasoning"], time_budget_min=60, tier="L2")
    big_total = sum(t["n"] for t in big["tasks"])
    small_total = sum(t["n"] for t in small["tasks"])
    assert big_total > small_total, \
        f"大 budget 应产生更多总样本: big={big_total} small={small_total}"


def test_compose_max_n_caps_n():
    p = compose_plan(["reasoning", "coding"], time_budget_min=120, tier="L2", max_n=15)
    for t in p["tasks"]:
        assert t["n"] <= 15


def test_compose_task_ids_valid():
    """composer 产的所有 benchmark id 必须在 configs/benchmarks.yaml 注册。"""
    p = compose_plan(["reasoning", "coding", "agent", "long_context", "multilingual",
                      "instruction_following"], time_budget_min=60, tier="L1")
    registered = load_benchmarks()
    for t in p["tasks"]:
        assert t["benchmark"] in registered, f"未注册: {t['benchmark']}"


def test_write_plan_roundtrip():
    import tempfile, yaml
    p = compose_plan(["reasoning"], time_budget_min=10, tier="L1", name="_test_tmp_plan")
    with tempfile.TemporaryDirectory() as d:
        path = write_plan(p, out_dir=d)
        assert path.exists()
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert loaded["name"] == p["name"]
        assert loaded["tasks"] == p["tasks"]


def test_cli_compose_executes():
    out = subprocess.run(
        [sys.executable, "scripts/run_benchmark.py", "compose",
         "--time-budget", "10", "--dimensions", "reasoning,coding",
         "--tier", "L1", "--max-n", "8", "--name", "_smoke_compose_test"],
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert out.returncode == 0, out.stderr
    assert "composed plan" in out.stdout
    p = Path(__file__).resolve().parents[1] / "plans" / "_smoke_compose_test" / "plan.yaml"
    assert p.exists(), "plan 文件未生成"
    p.unlink()
    p.parent.rmdir()


def _main():
    import traceback
    tests = [(n, globals()[n]) for n in list(globals())
             if n.startswith("test_") and callable(globals()[n])]
    tests.sort()
    p = f = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  test_composer::{name}")
            p += 1
        except Exception:
            print(f"  FAIL  test_composer::{name}")
            traceback.print_exc()
            f += 1
    print(f"=== {'OK' if f == 0 else 'FAIL'}: {p} passed, {f} failed ===")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(_main())
