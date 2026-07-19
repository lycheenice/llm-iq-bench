"""轻量测试运行器：无 pytest 也能跑。

用法：
    python tests/_runner.py              # 跑 tests/test_*.py 全部
    python tests/test_smoke.py           # 单文件（每个 test 文件末尾 callable _main()）

约定：每个 tests/test_*.py 顶层定义以 `test_` 开头的函数（参数 self 无），
本 runner 用 importlib 导入、扫描、逐个调用；assert 失败即记 AssertionError。
兼容 pytest：函数签名与命名风格不变，`pytest -q tests` 同样可用。
"""
from __future__ import annotations

import importlib.util
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_module(test_file: Path):
    name = test_file.stem
    spec = importlib.util.spec_from_file_location(name, test_file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def collect(mod) -> list:
    return sorted(
        [(n, getattr(mod, n)) for n in dir(mod) if n.startswith("test_") and callable(getattr(mod, n))],
        key=lambda x: x[0],
    )


def run_file(test_file: Path) -> tuple[int, int]:
    mod = load_module(test_file)
    tests = collect(mod)
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {test_file.name}::{name}")
            passed += 1
        except Exception:
            print(f"  FAIL  {test_file.name}::{name}")
            traceback.print_exc()
            failed += 1
    return passed, failed


def main(argv=None):
    files = [Path(a).resolve() for a in (argv or sys.argv[1:])]
    if not files:
        files = sorted(HERE.glob("test_*.py"))
    tp = tf = 0
    for f in files:
        print(f"== {f.name} ==")
        p, fl = run_file(f)
        tp += p
        tf += fl
    print(f"\n=== {'OK' if tf == 0 else 'FAIL'}: {tp} passed, {tf} failed ===")
    return 0 if tf == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
