"""多轮方差分析单测：build_variance_report 纯函数。

纯 python 可跑：`python3 tests/test_variance.py`
兼容 pytest。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_iq_bench.reporter import build_variance_report


def _run(plan, model, seed, ts, tasks):
    return {"plan": plan, "model": model, "seed": seed, "timestamp": ts, "tasks": tasks}


def test_variance_stable_tasks():
    runs = [
        _run("p", "m", 1, "t1", {"a": {"score": 0.80, "n": 10}, "b": {"score": 0.50, "n": 10}}),
        _run("p", "m", 2, "t2", {"a": {"score": 0.80, "n": 10}, "b": {"score": 0.50, "n": 10}}),
        _run("p", "m", 3, "t3", {"a": {"score": 0.80, "n": 10}, "b": {"score": 0.50, "n": 10}}),
    ]
    md = build_variance_report(runs)
    assert "✓" in md  # 极差 0 ≤ 0.05 稳定
    assert "0.000" in md  # 极差/标准差为 0


def test_variance_unstable_flagged():
    runs = [
        _run("p", "m", 1, "t1", {"a": {"score": 0.90, "n": 10}}),
        _run("p", "m", 2, "t2", {"a": {"score": 0.70, "n": 10}}),
    ]
    md = build_variance_report(runs)
    assert "✗" in md  # 极差 0.20 > 0.05 不稳定
    assert "0.200" in md  # 极差


def test_variance_excludes_skipped_errored():
    runs = [
        _run("p", "m", 1, "t1", {"a": {"score": 0.5, "n": 5}, "b": {"skipped": True, "reason": "x"}, "c": {"errored": True}}),
        _run("p", "m", 2, "t2", {"a": {"score": 0.6, "n": 5}, "b": {"skipped": True, "reason": "x"}, "c": {"errored": True}}),
    ]
    md = build_variance_report(runs)
    assert "| a |" in md
    assert "| b |" not in md and "| c |" not in md


def test_variance_empty_runs():
    md = build_variance_report([])
    assert "暂无" in md


def test_variance_overall_score_row():
    runs = [
        _run("p", "m", 1, "t1", {"a": {"score": 0.8, "n": 5}, "b": {"score": 0.6, "n": 5}}),
        _run("p", "m", 2, "t2", {"a": {"score": 0.8, "n": 5}, "b": {"score": 0.6, "n": 5}}),
    ]
    md = build_variance_report(runs)
    # 综合得分均分 = 0.7
    assert "0.700" in md
    assert "综合得分" in md


def test_variance_writes_file():
    runs = [_run("p", "m", 1, "t1", {"a": {"score": 0.5, "n": 5}}),
            _run("p", "m", 2, "t2", {"a": {"score": 0.5, "n": 5}})]
    out = Path("/tmp/_var_test.md")
    try:
        md = build_variance_report(runs, out_path=out)
        assert out.exists()
        assert "多轮稳定性报告" in md
    finally:
        out.unlink(missing_ok=True)


def _main():
    import traceback
    tests = [(n, globals()[n]) for n in list(globals())
             if n.startswith("test_") and callable(globals()[n])]
    tests.sort()
    p = f = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  test_variance::{name}")
            p += 1
        except Exception:
            print(f"  FAIL  test_variance::{name}")
            traceback.print_exc()
            f += 1
    print(f"=== {'OK' if f == 0 else 'FAIL'}: {p} passed, {f} failed ===")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(_main())
