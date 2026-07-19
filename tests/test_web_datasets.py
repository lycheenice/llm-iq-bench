"""P1 web 数据源单测：下载/缓存/解析 JSONL+CSV+TSV+JSON，不依赖网络。

纯 python 可跑：`python3 tests/test_web_datasets.py`
兼容 pytest。
"""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_iq_bench.datasets import _load_web, _parse, load_dataset_samples


# ---------- _parse 四格式 ----------

def test_parse_jsonl():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x.jsonl"
        p.write_text('{"q":"a","a":"1"}\n{"q":"b","a":"2"}\n', encoding="utf-8")
        rows = _parse(p, "jsonl", {})
        assert len(rows) == 2 and rows[0]["q"] == "a" and rows[1]["a"] == "2"


def test_parse_json_list():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x.json"
        p.write_text(json.dumps([{"q": "a"}, {"q": "b"}]), encoding="utf-8")
        rows = _parse(p, "json", {})
        assert len(rows) == 2 and rows[1]["q"] == "b"


def test_parse_json_dict_with_examples():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x.json"
        p.write_text(json.dumps({"canary": "x", "examples": [{"input": "a"}, {"input": "b"}]}), encoding="utf-8")
        rows = _parse(p, "json", {})
        assert len(rows) == 2 and rows[0]["input"] == "a"


def test_parse_csv():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x.csv"
        p.write_text("q,a\nfoo,1\nbar,2\n", encoding="utf-8")
        rows = _parse(p, "csv", {})
        assert len(rows) == 2 and rows[0]["q"] == "foo" and rows[1]["a"] == "2"


def test_parse_tsv_no_header_column_index():
    """TSV 无表头，fields 值为 int 列号。"""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x.tsv"
        p.write_text("Quel est 1+1?\t2\nCombien 3*4?\t12\n", encoding="utf-8")
        rows = _parse(p, "tsv", {"fields": {"question": 0, "gold": 1}})
        assert len(rows) == 2
        assert rows[0]["question"] == "Quel est 1+1?" and rows[0]["gold"] == "2"


# ---------- _load_web 缓存 + 下载 mock ----------

def _make_spec(url, fmt, fields=None, dim="reasoning"):
    return {
        "dim": dim, "source": "web", "url": url, "format": fmt,
        "fields": fields or {}, "version": "test",
    }


def test_load_web_caches_and_no_redownload():
    """第二次加载应命中缓存，不再次下载。"""
    spec = _make_spec("https://example.com/x.jsonl", "jsonl",
                      fields={"question": "q", "gold": "a"}, dim="_testcache")
    fake_content = b'{"q":"hi","a":"1"}\n{"q":"yo","a":"2"}\n'
    with patch("llm_iq_bench.datasets.requests.get") as mock_get, tempfile.TemporaryDirectory() as d:
        # 把 BUILTIN_DIR 临时指向 d，避免污染真实 datasets/
        with patch("llm_iq_bench.datasets.BUILTIN_DIR", Path(d)):
            mock_resp = MagicMock()
            mock_resp.content = fake_content
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp
            rows1 = _load_web(spec, "gsm8k_test")
            rows2 = _load_web(spec, "gsm8k_test")
        assert mock_get.call_count == 1, f"应只下载一次，实得 {mock_get.call_count}"
        assert len(rows1) == 2 and len(rows2) == 2
        assert rows1[0]["q"] == "hi"


def test_load_web_download_failure_raises():
    spec = _make_spec("https://example.com/missing.jsonl", "jsonl", dim="_testfail")
    with patch("llm_iq_bench.datasets.requests.get") as mock_get, tempfile.TemporaryDirectory() as d:
        with patch("llm_iq_bench.datasets.BUILTIN_DIR", Path(d)):
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = RuntimeError("404")
            mock_get.return_value = mock_resp
            try:
                _load_web(spec, "missing")
            except RuntimeError:
                return
    raise AssertionError("下载失败应抛 RuntimeError")


def test_load_web_gzip_url():
    """url 以 .gz 结尾时应 gzip 解压。"""
    import gzip as gz
    spec = _make_spec("https://example.com/x.jsonl.gz", "jsonl",
                      fields={"question": "q"}, dim="_testgz")
    raw = gz.compress(b'{"q":"a"}\n{"q":"b"}\n')
    with patch("llm_iq_bench.datasets.requests.get") as mock_get, tempfile.TemporaryDirectory() as d:
        with patch("llm_iq_bench.datasets.BUILTIN_DIR", Path(d)):
            mock_resp = MagicMock()
            mock_resp.content = raw
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp
            rows = _load_web(spec, "gz_test")
        assert len(rows) == 2 and rows[0]["q"] == "a"


# ---------- 字段映射集成 ----------

def test_load_dataset_samples_web_via_mock():
    """load_dataset_samples 对 source=web 走 _load_web（mock 网络）。"""
    cfg = {"webds_test": _make_spec("https://e.com/x.json", "json",
             fields={"question": "input"}, dim="reasoning")}
    with patch("llm_iq_bench.datasets.requests.get") as mock_get, tempfile.TemporaryDirectory() as d:
        with patch("llm_iq_bench.datasets.BUILTIN_DIR", Path(d)):
            mock_resp = MagicMock()
            mock_resp.content = json.dumps({"examples": [{"input": "Q1"}, {"input": "Q2"}]}).encode()
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp
            samples = load_dataset_samples("webds_test", cfg, n=None)
        assert len(samples) == 2 and samples[0]["input"] == "Q1"


# ---------- 现有 source 回归 ----------

def test_builtin_source_still_works():
    cfg = {
        "demo_mc": {"dim": "knowledge", "source": "builtin", "repo": "builtin:demo_mc",
                    "fields": {"question": "question", "choices": "choices", "gold": "answer"}}
    }
    s = load_dataset_samples("demo_mc", cfg)
    assert len(s) == 6 and s[0]["answer"] == "B"


def test_unknown_source_raises():
    cfg = {"x": {"source": "bogus"}}
    try:
        load_dataset_samples("x", cfg)
    except ValueError:
        return
    raise AssertionError("未知 source 应抛 ValueError")


# ---------- 真实网络（可选，默认跳过） ----------

def test_real_gsm8k_smoke():
    """真实下载 gsm8k 1 题（需网络）。失败时 skip 不算 fail。"""
    cfg = {"gsm8k": {
        "dim": "reasoning", "source": "web", "format": "jsonl",
        "url": "https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/test.jsonl",
        "version": "2023", "license": "MIT", "fields": {"question": "question", "gold": "answer"}, "n_default": 500,
    }}
    with tempfile.TemporaryDirectory() as d:
        with patch("llm_iq_bench.datasets.BUILTIN_DIR", Path(d)):
            try:
                s = load_dataset_samples("gsm8k", cfg, n=2)
            except Exception as e:
                print(f"    [skip] 网络不可达: {type(e).__name__}")
                return
    assert len(s) == 2 and "question" in s[0] and "answer" in s[0]


def _main():
    import traceback
    tests = [(n, globals()[n]) for n in list(globals())
             if n.startswith("test_") and callable(globals()[n])]
    tests.sort()
    p = f = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  test_web_datasets::{name}")
            p += 1
        except Exception:
            print(f"  FAIL  test_web_datasets::{name}")
            traceback.print_exc()
            f += 1
    print(f"=== {'OK' if f == 0 else 'FAIL'}: {p} passed, {f} failed ===")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(_main())
