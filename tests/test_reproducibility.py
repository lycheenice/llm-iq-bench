"""P0-2/3 可复现性单测：config_snapshot + seed 贯通 + errored 标记。

纯 python 可跑：`python3 tests/test_reproducibility.py`
兼容 pytest：`python3 -m pytest tests/test_reproducibility.py -q`
"""
import json
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_iq_bench.config import load_models, load_benchmarks
from llm_iq_bench.models import build_model_client, _mask_key
from llm_iq_bench.runner import _git_info, _default_seed, Runner
from llm_iq_bench.reporter import _render_run_md, _render_comparison


# ---------- 工具函数 ----------

def test_git_info_returns_keys():
    info = _git_info()
    assert isinstance(info, dict)
    assert "commit" in info and "dirty" in info and "branch" in info


def test_git_info_does_not_raise():
    # 多次调用稳定不抛（即便环境 git 不可用）
    for _ in range(3):
        _git_info()


def test_default_seed_stable_and_distinct():
    assert _default_seed("quick") == _default_seed("quick")
    assert _default_seed("quick") != _default_seed("full")


def test_mask_key():
    assert _mask_key("sk-abcdef1234") == "***1234"
    assert _mask_key("") == "***"
    assert _mask_key("ab") == "***"
    assert _mask_key("abcdefgh") == "***efgh"


# ---------- errored 标记 ----------

def test_errored_outcome_for_unimplemented_metric():
    """metric 是 truthfulqa_mc1（NotImplementedError），无 runner → outcome errored。

    注：ifeval_strict 在 P0-5 后已有 runner=ifeval，不再适合做 errored 夹具；
    改用 safety_truthfulqa（metric stub，无 runner）。
    """
    bench_cfg = load_benchmarks()
    assert "safety_truthfulqa" in bench_cfg
    r = Runner(model_id="mock", benchmarks_cfg=bench_cfg)
    with tempfile.TemporaryDirectory() as d:
        sf = Path(d) / "s.jsonl"
        with open(sf, "w", encoding="utf-8") as f:
            outcome = r._run_one("safety_truthfulqa", 3, f)
        samples_text = sf.read_text(encoding="utf-8").strip()
    assert outcome.get("errored") is True, f"应 errored: {outcome}"
    assert "reason" in outcome
    assert "score" not in outcome or outcome.get("score") in (None, 0.0)
    # samples 不应写出 errored 题目
    assert samples_text == ""


# ---------- config_snapshot ----------

def _run_quick_mock_snapshot(tmpdir: Path):
    """用 mock 跑 quick plan，返回 run_dir。"""
    r = Runner(model_id="mock")
    summary = r.run_plan(Path("plans/quick/plan.yaml").resolve())
    # run_dir = RESULTS_DIR / f"{plan}_{model}_{ts}"
    run_dir = Path(r._last_run_dir) if hasattr(r, "_last_run_dir") else None
    return summary, run_dir


def test_config_snapshot_written_and_fields():
    # 直接调 run_plan，再找最新 run_dir
    r = Runner(model_id="mock")
    r.run_plan(Path("plans/quick/plan.yaml").resolve())
    run_dir = Path(r._last_run_dir)
    snap = run_dir / "config_snapshot.yaml"
    assert snap.exists(), f"config_snapshot.yaml 未生成: {run_dir}"
    data = yaml.safe_load(snap.read_text(encoding="utf-8"))
    for key in ("plan", "model", "datasets", "benchmarks", "git", "seed", "timestamp"):
        assert key in data, f"snapshot 缺字段: {key}"
    # api_key 脱敏：mock 无 key，应不含裸密钥
    model_section = data.get("model") or {}
    assert "mock" in model_section
    mock_entry = model_section["mock"]
    key_val = mock_entry.get("api_key")
    assert key_val is None or key_val == "***" or str(key_val).startswith("***") or key_val in ("", "EMPTY"), \
        f"api_key 未脱敏: {key_val!r}"


def test_snapshot_git_commit_present():
    r = Runner(model_id="mock")
    r.run_plan(Path("plans/quick/plan.yaml").resolve())
    snap = yaml.safe_load((Path(r._last_run_dir) / "config_snapshot.yaml").read_text(encoding="utf-8"))
    g = snap["git"]
    # 本仓库已 git init，commit 应非 None
    assert g.get("commit"), f"git commit 缺失: {g}"


# ---------- seed 贯通 mock ----------

def test_mock_seed_reproducible():
    """同 seed 同 prompt → mock 输出一致。"""
    client_a = build_model_client("mock", load_models())
    client_a.seed = 1234
    client_b = build_model_client("mock", load_models())
    client_b.seed = 1234
    a = client_a.generate("Answer: pick A/B/C/D question one")
    b = client_b.generate("Answer: pick A/B/C/D question one")
    assert a == b, f"同 seed 应复现：a={a!r} b={b!r}"


def test_mock_seed_different_seed_changes_output():
    client_a = build_model_client("mock", load_models())
    client_a.seed = 1
    client_b = build_model_client("mock", load_models())
    client_b.seed = 9999
    # 多试几次提高差异概率
    diffs = 0
    for q in ["Answer: pick A/B/C/D q1", "Answer: pick A/B/C/D q2", "Answer: pick A/B/C/D q3"]:
        if client_a.generate(q) != client_b.generate(q):
            diffs += 1
    assert diffs > 0, "不同 seed 应改变输出"


# ---------- reporter 综合得分剔除 errored/skipped ----------

def test_reporter_overall_excludes_errored_skipped():
    summary = {
        "plan": "t", "model": "mock", "timestamp": "20260719T000000Z",
        "tasks": {
            "a": {"metric": "m", "score": 0.5, "n": 10},
            "b": {"errored": True, "reason": "x"},
            "c": {"skipped": True, "reason": "y"},
            "d": {"metric": "m", "score": 1.0, "n": 5},
        },
    }
    md = _render_run_md(summary, tag=None, run_dir=Path("results/x"))
    # 综合得分 = (0.5 + 1.0) / 2 = 0.75
    assert "0.750" in md, f"综合得分应剔除 errored/skipped = 0.75，md:\n{md}"


def test_comparison_excludes_errored():
    runs = [{
        "plan": "t", "model": "mock", "timestamp": "20260719T000000Z",
        "tasks": {"a": {"score": 0.4, "n": 5}, "b": {"errored": True, "reason": "x"}},
    }]
    md = _render_comparison(runs)
    # 只算 a：0.4
    assert "0.400" in md


# ---------- 纯 python 入口 ----------

def _main():
    import traceback
    tests = [(n, globals()[n]) for n in list(globals())
             if n.startswith("test_") and callable(globals()[n])]
    tests.sort()
    p = f = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  test_reproducibility::{name}")
            p += 1
        except Exception:
            print(f"  FAIL  test_reproducibility::{name}")
            traceback.print_exc()
            f += 1
    print(f"=== {'OK' if f == 0 else 'FAIL'}: {p} passed, {f} failed ===")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(_main())
