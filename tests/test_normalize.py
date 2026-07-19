"""字段规范化单测：load_dataset_samples 按 spec.fields 把源字段拷到标准名。

确保 prompts.render 能拿到 question/context/choices 等标准键，
即便原始数据集用 input/target/text 等不同键名。
纯 python 可跑：`python3 tests/test_normalize.py`
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_iq_bench.datasets import _normalize_sample, load_dataset_samples


def test_normalize_copies_source_to_canonical():
    sample = {"input": "Q1", "target": "Yes"}
    fields = {"question": "input", "gold": "target"}
    out = _normalize_sample(dict(sample), fields)
    assert out["question"] == "Q1"
    assert out["gold"] == "Yes"
    # 原键保留
    assert out["input"] == "Q1" and out["target"] == "Yes"


def test_normalize_no_override_existing_canonical():
    """已有标准键时不被覆盖（gsm8k 原生就有 question）。"""
    sample = {"question": "原生Q", "answer": "#### 42"}
    fields = {"question": "question", "gold": "answer"}
    out = _normalize_sample(dict(sample), fields)
    assert out["question"] == "原生Q"  # 不变
    assert out["answer"] == "#### 42"


def test_normalize_empty_fields_noop():
    sample = {"foo": 1}
    out = _normalize_sample(dict(sample), {})
    assert out == {"foo": 1}


def test_normalize_choices_list():
    sample = {"opts": ["A", "B"], "ans": 0}
    fields = {"choices": "opts", "gold": "ans"}
    out = _normalize_sample(dict(sample), fields)
    assert out["choices"] == ["A", "B"]
    assert out["gold"] == 0


def test_normalize_builtin_unaffected_regresion():
    """builtin demo_mc 原生键不变。"""
    cfg = {"demo_mc": {"dim": "k", "source": "builtin", "repo": "builtin:demo_mc",
                       "fields": {"question": "question", "choices": "choices", "gold": "answer"}}}
    s = load_dataset_samples("demo_mc", cfg)
    assert s[0]["question"] == "1+1=?"
    assert "choices" in s[0] and "answer" in s[0]


def test_normalize_local_via_mock_field_map():
    """模拟一个 source=local 的样本用非标准键，验证规范化接入。"""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x.jsonl"
        p.write_text('{"input":"Q","target":"T"}\n', encoding="utf-8")
        cfg = {"x": {"dim": "reasoning", "source": "local", "repo": str(p),
                     "fields": {"question": "input", "gold": "target"}}}
        s = load_dataset_samples("x", cfg)
        assert s[0]["question"] == "Q" and s[0]["gold"] == "T"
        assert s[0]["input"] == "Q"  # 原键保留


def _main():
    import traceback
    tests = [(n, globals()[n]) for n in list(globals())
             if n.startswith("test_") and callable(globals()[n])]
    tests.sort()
    p = f = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  test_normalize::{name}")
            p += 1
        except Exception:
            print(f"  FAIL  test_normalize::{name}")
            traceback.print_exc()
            f += 1
    print(f"=== {'OK' if f == 0 else 'FAIL'}: {p} passed, {f} failed ===")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(_main())
