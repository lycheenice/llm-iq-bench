"""B1 单测：suites/<dim>/definition.yaml.benchmarks 字段动态读，cli 不再依赖硬编码。

`python3 tests/test_suite_dynamic.py`
"""
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_iq_bench.config import load_suite, load_benchmarks


def test_definition_has_benchmarks_field():
    """每个 dim 的 definition.yaml 都应有 benchmarks 字段且非空。"""
    for dim in ["knowledge", "reasoning", "coding", "instruction_following",
                "safety", "agent", "multilingual", "long_context"]:
        s = load_suite(dim)
        bids = s.get("benchmarks")
        assert isinstance(bids, list) and len(bids) > 0, f"{dim} 缺 benchmarks 字段或为空"


def test_benchmarks_field_subset_of_configs():
    """definition.yaml.benchmarks 里的 id 全部应在 configs/benchmarks.yaml 中存在。"""
    registered = load_benchmarks()
    for dim in ["knowledge", "reasoning", "coding", "instruction_following",
                "safety", "agent", "multilingual", "long_context"]:
        s = load_suite(dim)
        for bid in s["benchmarks"]:
            assert bid in registered, f"{dim}.benchmarks 含未注册的 {bid}"


def test_dim_matches_dataset_dim():
    """definition.benchmarks 通过 dataset.dim 反推应等于 definition.dim。"""
    from llm_iq_bench.config import load_datasets
    datasets = load_datasets()
    registered = load_benchmarks()
    for dim in ["knowledge", "reasoning", "coding", "instruction_following",
                "safety", "agent", "multilingual", "long_context"]:
        s = load_suite(dim)
        for bid in s["benchmarks"]:
            ds = registered[bid].get("dataset")
            ds_dim = datasets.get(ds, {}).get("dim")
            assert ds_dim == dim, f"{bid} (dataset={ds}) 的 dim={ds_dim} != suite dim={dim}"


def test_cli_list_shows_benchmarks_count():
    """`list` 子命令输出应含每个 dim 的 benchmark 数。"""
    out = subprocess.run(
        [sys.executable, "scripts/run_benchmark.py", "list"],
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert out.returncode == 0, out.stderr
    assert "维度 suite" in out.stdout
    # 每个存在的 suite 都应出现 "[N tasks:" 标识
    lines = [l for l in out.stdout.splitlines() if "tasks:" in l]
    assert len(lines) >= 7, f"应至少 7 个 suite 显示 benchmark 数，实际 {len(lines)}:\n{out.stdout}"
    for l in lines:
        assert "[0 tasks:" not in l, f"发现空 suite: {l.strip()}"


def _main():
    import traceback
    tests = [(n, globals()[n]) for n in list(globals())
             if n.startswith("test_") and callable(globals()[n])]
    tests.sort()
    p = f = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  test_suite_dynamic::{name}")
            p += 1
        except Exception:
            print(f"  FAIL  test_suite_dynamic::{name}")
            traceback.print_exc()
            f += 1
    print(f"=== {'OK' if f == 0 else 'FAIL'}: {p} passed, {f} failed ===")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(_main())
