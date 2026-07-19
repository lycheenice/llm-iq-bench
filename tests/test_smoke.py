import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_iq_bench.config import load_models, load_datasets, load_benchmarks
from llm_iq_bench.metrics import compute_metric, _boxed
from llm_iq_bench.models import build_model_client
from llm_iq_bench.datasets import load_dataset_samples
from llm_iq_bench.prompts import render
from llm_iq_bench.executors import _score_bfcl, _needle_match, _exec_python, _extract_code, _build_tools


def test_configs_load():
    assert "mock" in load_models()
    assert "gsm8k" in load_datasets()
    assert "reasoning_gsm8k" in load_benchmarks()


def test_builtin_datasets():
    cfg = load_datasets()
    assert len(load_dataset_samples("demo_mc", cfg)) == 6
    assert len(load_dataset_samples("demo_qa", cfg)) == 6


def test_mock_client():
    client = build_model_client("mock", load_models())
    out = client.generate("Answer: pick A/B/C/D")
    assert isinstance(out, str) and len(out) > 0


def test_metrics_accuracy_mc():
    assert compute_metric("accuracy_mc", "B", "B", choices=["A", "B", "C"]) is True
    assert compute_metric("accuracy_mc", "The answer is A.", "A", choices=["A", "B", "C"]) is True
    assert compute_metric("accuracy_mc", "C", "B", choices=["A", "B", "C"]) is False


def test_metrics_numeric():
    assert compute_metric("exact_match_numeric", "The answer is 42.", "42") is True
    assert compute_metric("exact_match_numeric", "no number here", "42") is False


def test_metrics_boxed():
    assert compute_metric("exact_match_boxed", r"\boxed{7}", "7") is True
    assert compute_metric("exact_match_boxed", r"so \boxed{81}", "81") is True


def test_metrics_boxed_nested_and_text_wrapper():
    # 嵌套大括号 + \text{} 包裹
    assert _boxed(r"\boxed{\text{Yes}}") == "Yes"
    assert _boxed(r"x \boxed{\text{No}} end") == "No"
    assert _boxed(r"\boxed{42}") == "42"
    assert _boxed(r"a \boxed{1} b \boxed{2}") == "2"  # 取最后一个
    assert _boxed("no boxed here") is None


def test_prompt_render_mc():
    prompt = render("knowledge_mc", {"question": "Q?", "choices": ["x", "y"]})
    assert "A. x" in prompt and "B. y" in prompt


def test_refusal_metric():
    assert compute_metric("refusal_rate", "I'm sorry, I can't help.", None) is True
    assert compute_metric("refusal_rate", "Sure, here is how.", None) is False


def test_glm_local_model_config():
    cfg = load_models()
    assert "glm-local" in cfg
    c = build_model_client("glm-local", cfg)
    assert c.api_model_id == "glm"
    assert "localhost:8001" in c.base_url


def test_bfcl_scoring():
    gt = [{"calculate_triangle_area": {"base": [10], "height": [5], "unit": ["units", ""]}}]
    assert _score_bfcl([{"name": "calculate_triangle_area", "arguments": {"base": 10, "height": 5, "unit": "units"}}], gt) is True
    assert _score_bfcl([{"name": "calculate_triangle_area", "arguments": {"base": 10, "height": 5}}], gt) is True
    assert _score_bfcl([{"name": "calculate_triangle_area", "arguments": {"base": 99, "height": 5}}], gt) is False
    assert _score_bfcl([{"name": "calculate_triangle_area", "arguments": {"base": 10, "height": 5}}, {"name": "other", "arguments": {}}], gt) is False
    assert _score_bfcl([], None) is True
    assert _score_bfcl([{"name": "x", "arguments": {}}], None) is False


def test_bfcl_parallel_scoring():
    gt = [{"f1": {"a": [1]}}, {"f2": {"b": [2]}}]
    assert _score_bfcl([{"name": "f2", "arguments": {"b": 2}}, {"name": "f1", "arguments": {"a": 1}}], gt) is True
    assert _score_bfcl([{"name": "f1", "arguments": {"a": 1}}], gt) is False


def test_needle_match():
    assert _needle_match("The magic number for this session is 2824.", "2824") is True
    assert _needle_match("I don't know.", "2824") is False


def test_code_sandbox():
    assert _exec_python("def square(n):\n    return n * n\n\nassert square(3) == 9\n") is True
    assert _exec_python("def square(n):\n    return n\n\nassert square(3) == 9\n") is False


def test_code_sandbox_runs_setup_code():
    """MBPP 等数据集 test_setup_code 应在 asserts 前执行（构造 Node 等测试 fixture）。"""
    from llm_iq_bench.executors import _run_code_sandbox
    # 模拟 is_tree_balanced 类型：setup_code 建 Node 树，gold 用 root 变量
    fields = {"gold": "gold", "setup_code": "setup_code"}
    sample = {
        "gold": ["assert is_balanced(root) == True"],
        "setup_code": "class Node:\n    def __init__(self,v):\n        self.v=v;self.l=self.r=None\nroot = Node(1)",
    }
    # 正确实现：is_balanced 调用 root（来自 setup）应 pass
    code_ok = "def is_balanced(root):\n    return True"
    assert _run_code_sandbox(code_ok, sample, fields, "is_balanced") is True
    # 错实现：返回 False 应 fail
    code_bad = "def is_balanced(root):\n    return False"
    assert _run_code_sandbox(code_bad, sample, fields, "is_balanced") is False
    # 没 setup_code 时向后兼容
    sample_no = {"gold": ["assert f(2) == 4"]}
    assert _run_code_sandbox("def f(x):\n    return x*x", sample_no, {}, "f") is True


def test_mbpp_signature_extraction():
    """从 canonical code 提取完整签名，含双参数情形。"""
    from llm_iq_bench.executors import _mbpp_signature, _mbpp_expected_fn, _render_code_prompt
    fields = {"prompt": "text", "gold": "test_list", "canonical_code": "canonical_code"}
    sample = {
        "text": "Find frequency of largest value.",
        "canonical_code": "def frequency_Of_Largest(n, arr):\r\n    return arr.count(max(arr))",
        "test_list": ["assert frequency_Of_Largest(5,[1,2,3,4,4]) == 2"],
    }
    assert _mbpp_expected_fn(sample, fields) == "frequency_Of_Largest"
    sig = _mbpp_signature(sample, fields)
    assert sig == "def frequency_Of_Largest(n, arr):", f"got: {sig}"
    # prompt 应含 signature 提示
    p = _render_code_prompt("mbpp_task", sample, fields)
    assert "frequency_Of_Largest(n, arr)" in p, f"signature 未注入 prompt: {p}"
    assert "The function must be named `frequency_Of_Largest`" in p


def test_mbpp_signature_empty_when_no_code():
    """无 canonical code 时签名提示为空，prompt 退化为原行为。"""
    from llm_iq_bench.executors import _mbpp_signature, _render_code_prompt
    fields = {"prompt": "text", "gold": "test_list", "canonical_code": "canonical_code"}
    sample = {"text": "task text", "test_list": ["assert fn() == 1"]}
    assert _mbpp_signature(sample, fields) == ""
    p = _render_code_prompt("mbpp_task", sample, fields)
    assert "Use this exact function signature" not in p


def test_extract_code_fence():
    out = _extract_code("Here:\n```python\ndef f():\n    return 1\n```\ndone")
    assert "def f():" in out
    assert _extract_code("def g():\n    return 2").startswith("def g")


def test_build_tools_converts_dict_type():
    tools = _build_tools([{"name": "f", "description": "d", "parameters": {"type": "dict", "properties": {}}}])
    assert tools[0]["function"]["parameters"]["type"] == "object"


def _main():
    import traceback
    p = f = 0
    for name, fn in sorted([(n, globals()[n]) for n in list(globals()) if n.startswith("test_") and callable(globals()[n])]):
        try:
            fn()
            print(f"  PASS  test_smoke::{name}")
            p += 1
        except Exception:
            print(f"  FAIL  test_smoke::{name}")
            traceback.print_exc()
            f += 1
    print(f"=== {'OK' if f == 0 else 'FAIL'}: {p} passed, {f} failed ===")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(_main())
