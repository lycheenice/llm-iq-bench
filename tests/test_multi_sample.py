"""P0-1 多采样评测单测：maj@1 / pass@k / n>1 runner 路径。

纯 python 可跑：`python3 tests/test_multi_sample.py`
兼容 pytest：`python3 -m pytest tests/test_multi_sample.py -q`
"""
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_iq_bench.config import load_models, load_benchmarks
from llm_iq_bench.models import build_model_client
from llm_iq_bench.metrics import _last_number, _boxed, _norm_text


# ---------- maj_at_1 / aggregate 纯函数 ----------

def _extract(pred: str, kind: str | None) -> str:
    if kind == "last_number":
        n = _last_number(pred.replace(",", ""))
        return n if n is not None else _norm_text(pred)
    if kind == "boxed":
        b = _boxed(pred)
        return b if b is not None else _norm_text(pred)
    return _norm_text(pred)


def maj_at_1(predictions: list[str], gold, extractor: str | None = None) -> bool:
    normed = [_extract(p, extractor) for p in predictions]
    counts = Counter(normed)
    top, _ = counts.most_common(1)[0]
    return _norm_text(top) == _norm_text(gold)


def aggregate(agg: str, predictions: list[str], gold, extractor: str | None, metric_fn=None) -> bool:
    if agg == "maj@1":
        return maj_at_1(predictions, gold, extractor)
    if agg == "pass@k":
        if metric_fn is not None:
            return any(metric_fn(p, gold) for p in predictions)
        return any(_norm_text(_extract(p, extractor)) == _norm_text(gold) for p in predictions)
    raise ValueError(f"unknown aggregator: {agg}")


def test_maj_majority():
    assert maj_at_1(["The answer is 42.", "42", "answer: 7"], "42", "last_number") is True


def test_maj_minority_wrong():
    assert maj_at_1(["7", "42", "7"], "42", "last_number") is False


def test_maj_tie_picks_first_seen():
    # 42 与 7 各 1 票，Counter.most_common 取首次出现 → 42
    assert maj_at_1(["42", "7"], "42", "last_number") is True
    assert maj_at_1(["7", "42"], "42", "last_number") is False


def test_aggregate_pass_at_k_any_correct():
    preds = ["The answer is 7.", "The answer is 42.", "no number"]
    assert aggregate("pass@k", preds, "42", "last_number") is True
    assert aggregate("pass@k", preds, "99", "last_number") is False


def test_aggregate_unknown_raises():
    try:
        aggregate("bogus", ["a"], "a", None)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


# ---------- mock generate_n 长度 ----------

def test_mock_generate_n_length():
    client = build_model_client("mock", load_models())
    preds = client.generate_n("Answer: pick A/B/C/D", 4)
    assert isinstance(preds, list) and len(preds) == 4
    assert all(isinstance(p, str) and len(p) > 0 for p in preds)


# ---------- runner 多采样集成（mock + reasoning_aime 配置） ----------

def _run_aime_mock_one_sample(tmpdir: Path):
    """构造 Runner，只跑 reasoning_aime 1 题，返回写出的 samples 行。"""
    from llm_iq_bench.runner import Runner
    # 用内置 demo_qa 冒充 aime 数据集样本：把 reasoning_aime 临时指向 demo_qa
    # 更简单：直接调 _run_one，但需让数据集可加载。demo_qa 6 题可用。
    # 做法：patch benchmarks[reasoning_aime].dataset = demo_qa
    bench_cfg = load_benchmarks()
    bench_cfg["reasoning_aime"] = {
        "dataset": "demo_qa",
        "metric": "exact_match_numeric",
        "answer_extractor": "last_number",
        "prompt_template": "reasoning_qa",
        "params": {"temperature": 0.7, "max_tokens": 2048, "n": 4},
        "aggregator": "maj@1",
    }
    r = Runner(model_id="mock", benchmarks_cfg=bench_cfg)
    samples_path = tmpdir / "samples.jsonl"
    with open(samples_path, "w", encoding="utf-8") as f:
        outcome = r._run_one("reasoning_aime", 1, f)
    rows = [json.loads(l) for l in samples_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return outcome, rows


def test_runner_multisample_path_writes_n_predictions():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        outcome, rows = _run_aime_mock_one_sample(Path(d))
    assert len(rows) == 1
    rec = rows[0]
    assert "n_predictions" in rec, f"多采样分支应写 n_predictions，实得: {list(rec.keys())}"
    assert isinstance(rec["n_predictions"], list) and len(rec["n_predictions"]) == 4
    assert rec.get("aggregator") == "maj@1"
    assert "verdict" in rec and rec["verdict"] is not None
    assert outcome["n"] == 1


def test_single_sample_path_no_n_predictions():
    """n 缺省时走单采样原路径，samples 不含 n_predictions（向后兼容）。"""
    import tempfile
    from llm_iq_bench.runner import Runner
    bench_cfg = load_benchmarks()
    bench_cfg["reasoning_gsm8k"] = {
        "dataset": "demo_qa",
        "metric": "exact_match_numeric",
        "answer_extractor": "last_number",
        "prompt_template": "reasoning_qa",
        "params": {"temperature": 0, "max_tokens": 256},
    }
    r = Runner(model_id="mock", benchmarks_cfg=bench_cfg)
    with tempfile.TemporaryDirectory() as d:
        samples_path = Path(d) / "s.jsonl"
        with open(samples_path, "w", encoding="utf-8") as f:
            r._run_one("reasoning_gsm8k", 1, f)
        rows = [json.loads(l) for l in samples_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 1
    assert "n_predictions" not in rows[0], "单采样不应写 n_predictions"


# ---------- 纯函数: pass_at_k_unbiased (A3) ----------

def test_pass_at_k_unbiased_known_values():
    from llm_iq_bench.metrics import pass_at_k_unbiased
    assert pass_at_k_unbiased(5, 0, 1) == 0.0
    assert abs(pass_at_k_unbiased(5, 1, 1) - 0.2) < 1e-9
    assert pass_at_k_unbiased(5, 5, 1) == 1.0
    assert pass_at_k_unbiased(5, 1, 5) == 1.0  # k=n, 任一对, 退化
    # 1 - C(8,2)/C(10,2) = 1 - 28/45 = 0.3778
    assert abs(pass_at_k_unbiased(10, 2, 2) - (1 - 28/45)) < 1e-9


def test_pass_at_k_unbiased_invalid_raises():
    from llm_iq_bench.metrics import pass_at_k_unbiased
    for bad in [(0, 0, 1), (5, 0, 0), (5, 0, 6)]:
        try:
            pass_at_k_unbiased(*bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad}")


def test_pass_at_k_unbiased_monotonic_in_c():
    """c 越大 pass@k 越大（同 n,k）"""
    from llm_iq_bench.metrics import pass_at_k_unbiased
    vals = [pass_at_k_unbiased(10, c, 3) for c in range(0, 9)]
    assert vals == sorted(vals), f"should be monotonic: {vals}"


# ---------- A3: code_exec multisample 双报路径 ----------

def _run_code_exec_mock(tmpdir: Path, n_samples=None, n_problems=2):
    """构造 mock 跑 coding_humaneval（demo_qa 冒充），返回 outcome + rows。"""
    from llm_iq_bench.runner import Runner
    bench_cfg = load_benchmarks()
    params = {"temperature": 0.7, "max_tokens": 256, "concurrency": 2}
    if n_samples:
        params["n"] = n_samples
    bench_cfg["coding_humaneval"] = {
        "dataset": "demo_qa",  # 6 题，不真跑 sandbox（mock 输出文本，extract_code 可能失败但路径走通）
        "metric": "pass_at_1",
        "runner": "code_exec",
        "prompt_template": "code_complete",
        "params": params,
    }
    r = Runner(model_id="mock", benchmarks_cfg=bench_cfg)
    sp = tmpdir / "s.jsonl"
    with open(sp, "w", encoding="utf-8") as f:
        outcome = r._run_one("coding_humaneval", n_problems, f)
    rows = [json.loads(l) for l in sp.read_text(encoding="utf-8").splitlines() if l.strip()]
    return outcome, rows


def test_code_exec_multisample_writes_n_predictions_and_unbiased():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        outcome, rows = _run_code_exec_mock(Path(d), n_samples=5, n_problems=2)
    assert len(rows) == 2
    for r in rows:
        assert "n_predictions" in r and len(r["n_predictions"]) == 5
        assert "verdicts" in r and len(r["verdicts"]) == 5
        assert "c" in r and "n_samples" in r and r["n_samples"] == 5
        assert "pass_at_1_local" in r and "pass_at_k_unbiased" in r
        # c=0 时 unbiased=0；c>=1 时 unbiased>=0
        if r["c"] == 0:
            assert r["pass_at_k_unbiased"] == 0.0
    # outcome 双报
    assert outcome["metric"] == "pass_at_k"
    assert "pass_at_1" in outcome and "pass_at_k" in outcome
    assert outcome["n_samples"] == 5


def test_code_exec_single_sample_backward_compatible():
    """n 缺省时走原 pass_at_1 路径，samples 无 n_predictions。"""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        outcome, rows = _run_code_exec_mock(Path(d), n_samples=None, n_problems=2)
    assert outcome["metric"] == "pass_at_1"
    assert "pass_at_1" not in outcome and "pass_at_k" not in outcome  # 双报字段不出现
    for r in rows:
        assert "n_predictions" not in r and "prediction" in r
        assert "c" not in r


# ---------- A2: list aggregator 双报路径 ----------

def _run_aime_mini_mock(tmpdir: Path, n: int = 3):
    """跑 reasoning_aime_mini（builtin:aime_2024) mock 多采样，返回 outcome + rows。"""
    from llm_iq_bench.runner import Runner
    bench_cfg = load_benchmarks()
    r = Runner(model_id="mock", benchmarks_cfg=bench_cfg)
    samples_path = tmpdir / "samples.jsonl"
    with open(samples_path, "w", encoding="utf-8") as f:
        outcome = r._run_one("reasoning_aime_mini", n, f)
    rows = [json.loads(l) for l in samples_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return outcome, rows


def test_aime_mini_dataset_loads():
    """aime_2024 builtin 3 题可加载，gold 都是整数。"""
    from llm_iq_bench.datasets import load_dataset_samples
    from llm_iq_bench.config import load_datasets
    samples = load_dataset_samples("aime_2024", load_datasets(), n=3)
    assert len(samples) == 3
    for s in samples:
        assert "question" in s and "gold" in s
        assert isinstance(s["gold"], int) and 0 <= s["gold"] <= 999


def test_list_aggregator_writes_verdicts_and_outcome_aggregators():
    """list aggregator：samples 含 verdicts dict，outcome 含 aggregators 双报。"""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        outcome, rows = _run_aime_mini_mock(Path(d), n=3)
    assert len(rows) == 3
    for r in rows:
        assert r.get("aggregators") == ["maj@1", "pass@k"], f"aggregators 应双报: {r.get('aggregators')}"
        assert "verdicts" in r and isinstance(r["verdicts"], dict)
        assert set(r["verdicts"].keys()) == {"maj@1", "pass@k"}
        # primary 兼容字段：verdict == verdicts[maj@1]
        assert r.get("verdict") == r["verdicts"]["maj@1"]
    # outcome 双报
    assert outcome.get("aggregator") == ["maj@1", "pass@k"]
    assert "aggregators" in outcome, "outcome 应有 aggregators 双报字段"
    assert set(outcome["aggregators"].keys()) == {"maj@1", "pass@k"}
    assert outcome["n_samples"] == 4
    # pass@k >= maj@1 （任一正确 vs 多数投票，逻辑上必然）
    assert outcome["aggregators"]["pass@k"] >= outcome["aggregators"]["maj@1"]


def test_str_aggregator_backward_compatible():
    """str aggregator 路径不变（仅 outcome.aggregator 是 str，无 aggregators 字段）。"""
    import tempfile
    from llm_iq_bench.runner import Runner
    bench_cfg = load_benchmarks()
    bench_cfg["reasoning_aime"] = {
        "dataset": "aime_2024",
        "metric": "exact_match_numeric",
        "answer_extractor": "last_number",
        "prompt_template": "reasoning_qa",
        "params": {"temperature": 0.7, "max_tokens": 2048, "n": 4},
        "aggregator": "maj@1",  # str
    }
    r = Runner(model_id="mock", benchmarks_cfg=bench_cfg)
    with tempfile.TemporaryDirectory() as d:
        sp = Path(d) / "s.jsonl"
        with open(sp, "w", encoding="utf-8") as f:
            outcome = r._run_one("reasoning_aime", 2, f)
        rows = [json.loads(l) for l in sp.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert outcome["aggregator"] == "maj@1"  # str 保留
    assert "aggregators" not in outcome, "str aggregator 不应触发 aggregators 双报字段"
    for r in rows:
        assert r.get("aggregator") == "maj@1"
        # str 路径也写 verdicts（aggregators=[maj@1]），但单元素无 aggregators 字段
        assert "verdicts" in r and r["verdicts"].get("maj@1") is not None


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
            print(f"  PASS  test_multi_sample::{name}")
            p += 1
        except Exception:
            print(f"  FAIL  test_multi_sample::{name}")
            traceback.print_exc()
            f += 1
    print(f"=== {'OK' if f == 0 else 'FAIL'}: {p} passed, {f} failed ===")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(_main())
