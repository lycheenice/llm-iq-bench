"""P0-5 IFEval 校验器 + 执行器单测。

纯 python 可跑：`python3 tests/test_ifeval.py`
兼容 pytest。
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_iq_bench.ifeval_checker import check_instruction, score_response


# ---------- 单指令校验 ----------

def test_num_sentences_strict_pass():
    assert check_instruction("length_constraint:num_sentences",
                             {"num_sentences": 2}, "Hello world. Good bye.", True) is True


def test_num_sentences_strict_fail():
    assert check_instruction("length_constraint:num_sentences",
                             {"num_sentences": 2}, "Hello world. Good bye. More here.", True) is False


def test_num_sentences_loose_width():
    # strict=False，差 1 句也算 pass
    assert check_instruction("length_constraint:num_sentences",
                             {"num_sentences": 2}, "Hello world. Good bye. Extra.", True) is False
    assert check_instruction("length_constraint:num_sentences",
                             {"num_sentences": 2}, "Hello world. Good bye. Extra.", False) is True


def test_num_words():
    assert check_instruction("length_constraint:num_words",
                             {"num_words": 3}, "one two three", True) is True
    assert check_instruction("length_constraint:num_words",
                             {"num_words": 3}, "one two", True) is False


def test_number_bullet_lists():
    r = "1. first\n2. second\n3. third"
    assert check_instruction("detectable_format:number_bullet_lists",
                             {"num_bullets": 3}, r, True) is True
    assert check_instruction("detectable_format:number_bullet_lists",
                             {"num_bullets": 2}, r, True) is False


def test_json_format_strict():
    assert check_instruction("detectable_format:json_format", {}, '{"a": 1}', True) is True
    assert check_instruction("detectable_format:json_format", {}, '[1, 2]', True) is False  # strict 要 dict
    assert check_instruction("detectable_format:json_format", {}, 'not json', True) is False
    # fence 也认
    assert check_instruction("detectable_format:json_format", {}, '```json\n{"a": 1}\n```', True) is True


def test_no_comma():
    assert check_instruction("punctuation:no_comma", {}, "yes no maybe", True) is True
    assert check_instruction("punctuation:no_comma", {}, "yes, no", True) is False
    assert check_instruction("punctuation:no_comma", {}, "是的，不对", True) is False


def test_quotation():
    assert check_instruction("startend:quotation", {}, '"hello"', True) is True
    assert check_instruction("startend:quotation", {}, 'hello', True) is False


def test_capital_word():
    assert check_instruction("case:capital_word", {}, "Hello World", True) is True
    assert check_instruction("case:capital_word", {}, "Hello world", True) is False


def test_chinese_only():
    assert check_instruction("language:chinese_only", {}, "这是一段中文", True) is True
    assert check_instruction("language:chinese_only", {}, "这是 English 混", True) is False


def test_unknown_instruction_returns_false():
    assert check_instruction("bogus:id", {}, "anything", True) is False
    assert check_instruction("bogus:id", {}, "anything", False) is False  # 不崩


# ---------- score_response 聚合 ----------

def test_score_response_aggregation():
    response = "Yes. No."  # 2 句
    instructions = [
        {"instruction_id": "length_constraint:num_sentences", "kwargs": {"num_sentences": 2}},
        {"instruction_id": "punctuation:no_comma", "kwargs": {}},
        {"instruction_id": "detectable_format:json_format", "kwargs": {}},  # fail
    ]
    sc = score_response(response, instructions, strict=True)
    assert sc["total"] == 3
    assert sc["passed"] == 2
    assert sc["details"][2]["passed"] is False


def test_score_response_empty_instructions():
    sc = score_response("any", [], strict=True)
    assert sc["total"] == 0 and sc["passed"] == 0


# ---------- executor 集成（mock + builtin mini） ----------

def _run_ifeval_mock(tmpdir: Path):
    from llm_iq_bench.config import load_benchmarks
    from llm_iq_bench.runner import Runner
    bench_cfg = load_benchmarks()
    # 把 ifeval_strict 临时指向 ifeval_mini（builtin，离线可跑）
    bench_cfg["ifeval_strict"] = {
        "dataset": "ifeval_mini",
        "metric": "ifeval_strict",
        "runner": "ifeval",
        "prompt_template": "raw",
        "params": {"temperature": 0, "max_tokens": 256},
    }
    r = Runner(model_id="mock", benchmarks_cfg=bench_cfg)
    sf = tmpdir / "s.jsonl"
    with open(sf, "w", encoding="utf-8") as f:
        outcome = r._run_one("ifeval_strict", None, f)
    rows = [json.loads(l) for l in sf.read_text(encoding="utf-8").splitlines() if l.strip()]
    return outcome, rows


def test_run_ifeval_mock_integration():
    with tempfile.TemporaryDirectory() as d:
        outcome, rows = _run_ifeval_mock(Path(d))
    assert not outcome.get("errored"), f"不应 errored: {outcome}"
    assert not outcome.get("skipped"), f"不应 skipped: {outcome}"
    assert "score" in outcome, f"应有 score: {outcome}"
    assert outcome["metric"] == "ifeval_strict"
    assert len(rows) > 0, "应写出 samples"
    for r in rows:
        assert "prediction" in r and "instructions" in r and "verdict" in r
        assert "strict_pass_rate" in r
    # builtin 至少 6 条
    assert outcome["n"] >= 6


def test_dispatch_routes_ifeval():
    from llm_iq_bench.executors import dispatch
    # dispatch 对未知 runner 返回 skipped；ifeval 应被路由（非 unknown）
    # 用一个最小 bench/spec 验证 dispatch 认得 "ifeval"
    class _Dummy:
        datasets_cfg = {}
        client = None
    out = dispatch("ifeval", _Dummy(), {"dataset": "ifeval_mini", "params": {}}, {"source": "builtin"}, None, None)
    # client None 会崩，但崩点应在 run_ifeval 内部（非 unknown 路由），而非 dispatch 返回 unknown
    assert not (out.get("skipped") and "unknown runner" in out.get("reason", "")), \
        "ifeval 应被 dispatch 路由，不应返回 unknown runner"


def _main():
    import traceback
    tests = [(n, globals()[n]) for n in list(globals())
             if n.startswith("test_") and callable(globals()[n])]
    tests.sort()
    p = f = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  test_ifeval::{name}")
            p += 1
        except Exception:
            print(f"  FAIL  test_ifeval::{name}")
            traceback.print_exc()
            f += 1
    print(f"=== {'OK' if f == 0 else 'FAIL'}: {p} passed, {f} failed ===")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(_main())
