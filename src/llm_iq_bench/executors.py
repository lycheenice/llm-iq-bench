"""专用执行器。runner.py 把 bench.runner 字段分发到本模块。

三种执行器：
  - code_exec      : HumanEval / MBPP，沙箱跑测试，pass@1
  - needle_gen     : 大海捞针，深度×长度网格，exact_match
  - function_exec  : BFCL，模型 tools 调用 vs ground_truth

每个执行器返回 {"metric","score","n","total"} 或 {"skipped":True,"reason":...}，
并把逐题结果写入 samples_file。
"""
from __future__ import annotations

import json
import os
import random
import re
import resource
import subprocess
import sys
import tempfile
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(it, *_a, **_k):
        return it

ROOT = Path(__file__).resolve().parents[2]


def dispatch(runner_kind: str, runner, bench: dict, spec: dict, n, samples_file) -> dict:
    if runner_kind == "code_exec":
        return run_code_exec(runner, bench, spec, n, samples_file)
    if runner_kind == "needle_gen":
        return run_needle_gen(runner, bench, spec, n, samples_file)
    if runner_kind == "function_exec":
        return run_function_exec(runner, bench, spec, n, samples_file)
    if runner_kind == "ifeval":
        return run_ifeval(runner, bench, spec, n, samples_file)
    return {"skipped": True, "reason": f"unknown runner: {runner_kind}"}


def _concurrency(bench: dict, default: int = 8) -> int:
    c = int(bench.get("params", {}).get("concurrency", default))
    return max(1, c)


def _run_pool(work, items, concurrency, desc, **tqdm_kw):
    """并发处理 items，work(item)->dict。实时写回并显示进度，按完成顺序返回。"""
    out = []
    if concurrency <= 1:
        for it in tqdm(items, desc=desc, **tqdm_kw):
            out.append(work(it))
        return out
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = {ex.submit(work, it): i for i, it in enumerate(items)}
        for f in tqdm(as_completed(futs), total=len(futs), desc=desc, **tqdm_kw):
            out.append(f.result())
    return out


# ============================ code_exec ============================

def run_code_exec(runner, bench: dict, spec: dict, n, samples_file) -> dict:
    from .datasets import load_dataset_samples
    dataset_id = bench["dataset"]
    fields = spec.get("fields", {})
    try:
        samples = load_dataset_samples(dataset_id, runner.datasets_cfg, n=n)
    except Exception as e:
        print(f"[skip] {bench.get('') or bench['dataset']}: 数据集加载失败 — {e}")
        return {"skipped": True, "reason": f"dataset load failed: {type(e).__name__}: {e}"}

    template = bench.get("prompt_template", "code_complete")
    params = {k: v for k, v in bench.get("params", {}).items() if k != "concurrency"}
    concurrency = _concurrency(bench)
    # A3: n>1 走多采样 pass@k 无偏估计路径；n 缺省/=1 走原 pass_at_1 单采样路径
    n_samples = params.pop("n", None)
    multisample = bool(n_samples and n_samples > 1)

    def work(sample):
        prompt = _render_code_prompt(template, sample, fields)
        ep = sample.get(fields.get("entry_point", "entry_point"))
        if multisample:
            preds = runner.client.generate_n(prompt, int(n_samples), **params)
            ep_list = []
            verdicts = []
            errs = []
            for pred in preds:
                err = None
                try:
                    code = _extract_code(pred)
                except Exception as e:
                    code = ""
                    err = f"{type(e).__name__}: {e}"
                if not ep:
                    ep_l = _guess_entry_point(code, sample, fields)
                else:
                    ep_l = ep
                ep_list.append(ep_l)
                try:
                    ok = _run_code_sandbox(code, sample, fields, ep_l)
                except Exception as e:
                    ok = False
                    err = f"{type(e).__name__}: {e}"
                verdicts.append(bool(ok))
                errs.append(err)
            c = sum(verdicts)
            from .metrics import pass_at_k_unbiased
            unbiased = pass_at_k_unbiased(int(n_samples), c, int(n_samples)) if c < int(n_samples) else 1.0
            # pass@1 empirical = c/n; pass@k unbiased = unbiased
            rec = {
                "benchmark": bench.get("dataset", "code_exec"),
                "dataset": dataset_id,
                "prompt": prompt,
                "n_predictions": preds,
                "verdicts": verdicts,
                "gold": sample.get(fields.get("gold", "gold")),
                "entry_point": ep_list[0] if ep_list else ep,
                "c": c,
                "n_samples": int(n_samples),
                "pass_at_1_local": round(c / int(n_samples), 4),
                "pass_at_k_unbiased": round(unbiased, 4),
                "verdict": c > 0,  # 向后兼容：任一对
            }
            errs_filt = [e for e in errs if e]
            if errs_filt:
                rec["errors"] = errs_filt
            return rec
        err = None
        try:
            pred = runner.client.generate(prompt, **params)
        except Exception as e:
            pred = ""
            err = f"{type(e).__name__}: {e}"
        code = _extract_code(pred)
        ep_l = ep or _guess_entry_point(code, sample, fields)
        ok = _run_code_sandbox(code, sample, fields, ep_l)
        rec = {
            "benchmark": bench.get("dataset", "code_exec"),
            "dataset": dataset_id,
            "prompt": prompt,
            "prediction": pred,
            "gold": sample.get(fields.get("gold", "gold")),
            "entry_point": ep_l,
            "verdict": ok,
        }
        if err:
            rec["error"] = err
        return rec

    records = _run_pool(work, samples, concurrency, desc=bench.get("dataset", "code_exec"))
    for r in records:
        samples_file.write(json.dumps(r, ensure_ascii=False) + "\n")
    samples_file.flush()
    if multisample:
        n_total = len(records)
        pass1 = sum(r["pass_at_1_local"] for r in records) / n_total if n_total else 0.0
        passk = sum(r["pass_at_k_unbiased"] for r in records) / n_total if n_total else 0.0
        any_ok = sum(1 for r in records if r["c"] > 0) / n_total if n_total else 0.0
        return {
            "metric": "pass_at_k",
            "score": round(passk, 4),  # primary = pass@k unbiased（业界标准）
            "pass_at_1": round(pass1, 4),
            "pass_at_k": round(passk, 4),
            "any_correct_rate": round(any_ok, 4),
            "n_samples": int(n_samples),
            "n": n_total,
            "total": len(samples),
        }
    correct = sum(1 for r in records if r["verdict"])
    return {
        "metric": "pass_at_1",
        "score": round(correct / len(records), 4) if records else 0.0,
        "n": len(records),
        "total": len(samples),
    }


def _render_code_prompt(template: str, sample: dict, fields: dict) -> str:
    if template == "mbpp_task":
        task = sample[fields.get("prompt", "text")]
        ep = _mbpp_expected_fn(sample, fields)
        hint = f"\n\nThe function must be named `{ep}`." if ep else ""
        return f"Write a Python function to solve the following task. Only output code, no explanation.{hint}\n\n{task}"
    prompt_text = sample.get(fields.get("prompt", "prompt"), "")
    return f"Complete the following Python function. Only output code, no explanation.\n\n{prompt_text}"


def _mbpp_expected_fn(sample: dict, fields: dict) -> str:
    """从 MBPP 的 canonical code / test_list 推断期望的函数名。"""
    code = sample.get("code") or ""
    m = re.search(r"def\s+(\w+)\s*\(", code)
    if m:
        return m.group(1)
    for t in sample.get(fields.get("gold", "test_list"), []) or []:
        m = re.match(r"assert\s+(\w+)\s*\(", str(t))
        if m:
            return m.group(1)
    return ""


def _extract_code(pred: str) -> str:
    if not pred:
        return ""
    fences = re.findall(r"```(?:python)?\s*\n(.*?)```", pred, re.DOTALL)
    if fences:
        return textwrap.dedent(fences[-1]).strip()
    return pred.strip()


def _guess_entry_point(code: str, sample: dict, fields: dict) -> str:
    m = re.search(r"def\s+(\w+)\s*\(", code)
    return m.group(1) if m else ""


def _run_code_sandbox(code: str, sample: dict, fields: dict, entry_point: str) -> bool:
    gold = sample.get(fields.get("gold", "gold"))
    full = code + "\n\n"
    if isinstance(gold, str) and "def check" in gold:
        full += gold + f"\ncheck({entry_point})\n"
    elif isinstance(gold, list):
        full += "\n".join(gold) + "\n"
    else:
        return False
    return _exec_python(full)


def _exec_python(code: str, timeout: int = 12, mem_mb: int = 512) -> bool:
    def _limit():
        try:
            resource.setrlimit(resource.RLIMIT_AS, (mem_mb * 1024 * 1024, mem_mb * 1024 * 1024))
        except Exception:
            pass
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "sol.py"
        path.write_text(code, encoding="utf-8")
        try:
            r = subprocess.run(
                [sys.executable, str(path)], cwd=d, timeout=timeout,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, preexec_fn=_limit,
            )
            return r.returncode == 0
        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False


# ============================ needle_gen ============================

# NeedleHaystack 生成中文无关段落作填充，针随机插入深度×长度网格。
_FILLER = [
    "巴黎是法国的首都，以埃菲尔铁塔和卢浮宫闻名于世。",
    "光合作用是植物利用阳光将水和二氧化碳转化为葡萄糖的过程。",
    "长城是中国古代的军事防御工程，绵延超过两万公里。",
    "水的化学式是 H2O，由两个氢原子和一个氧原子组成。",
    "DNA 是一种双螺旋结构的生物大分子，携带着遗传信息。",
    "地球绕太阳公转一周大约需要 365.25 天。",
    "圆周率 π 是一个无理数，约等于 3.14159。",
    "宋代毕昇发明了活字印刷术，推动了知识的传播。",
    "鲸鱼是哺乳动物，需要浮出水面呼吸空气。",
    "罗马帝国曾是横跨欧亚非三大洲的强大帝国。",
]


def run_needle_gen(runner, bench: dict, spec: dict, n, samples_file) -> dict:
    params = bench.get("params", {})
    lengths = params.get("lengths", [4000, 16000, 32000])
    depths = params.get("depths", [0.1, 0.5, 0.9])
    seed = params.get("seed", 42)
    gen_params = {k: v for k, v in params.items() if k not in ("lengths", "depths", "needle_id", "seed", "concurrency")}
    concurrency = _concurrency(bench)
    rng = random.Random(seed)

    cases = [(L, d) for L in lengths for d in depths]
    if n is not None:
        cases = cases[:n]

    def work(case):
        length, depth = case
        context, needle, question, gold = _build_needle(length, depth, rng)
        prompt = f"Read the following passage and answer.\n\n{context}\n\nQuestion: {question}"
        err = None
        try:
            pred = runner.client.generate(prompt, **gen_params)
        except Exception as e:
            pred = ""
            err = f"{type(e).__name__}: {e}"
        ok = _needle_match(pred, gold)
        rec = {
            "benchmark": "long_needle",
            "dataset": "needle",
            "length_tokens": length,
            "depth": depth,
            "prompt_chars": len(prompt),
            "needle": needle,
            "gold": gold,
            "prediction": pred,
            "verdict": ok,
        }
        if err:
            rec["error"] = err
        return rec

    records = _run_pool(work, cases, concurrency, desc="needle_gen")
    correct = sum(1 for r in records if r["verdict"])
    for r in records:
        samples_file.write(json.dumps(r, ensure_ascii=False) + "\n")
    samples_file.flush()
    return {
        "metric": "exact_match_text",
        "score": round(correct / len(records), 4) if records else 0.0,
        "n": len(records),
        "total": len(cases),
    }


def _build_needle(length_tokens: int, depth: float, rng: random.Random):
    token_budget = length_tokens
    body = []
    char_count = 0
    i = 0
    while char_count < token_budget * 3.5:
        body.append(_FILLER[i % len(_FILLER)])
        char_count += len(body[-1])
        i += 1
    total = len(body)
    pos = max(1, min(total - 2, int(depth * total)))
    number = rng.randint(1000, 9999)
    needle = f"The magic number for this session is {number}."
    question = "What is the magic number for this session?"
    gold = str(number)
    body.insert(pos, needle)
    return "\n".join(body), needle, question, gold


def _needle_match(pred: str, gold: str) -> bool:
    if not pred:
        return False
    norm = re.sub(r"[^\w]", "", pred.lower())
    return gold.lower() in norm


# ============================ function_exec ============================

def run_function_exec(runner, bench: dict, spec: dict, n, samples_file) -> dict:
    repo = spec.get("repo", "/data1/datasets/bfcl")
    repo_path = Path(repo) if os.path.isabs(repo) else ROOT / repo
    categories = bench.get("params", {}).get("categories") or spec.get("categories") or ["simple"]
    pairs = []
    for cat in categories:
        inp = repo_path / f"BFCL_v3_{cat}.json"
        ans = repo_path / "possible_answer" / f"BFCL_v3_{cat}.json"
        if not inp.exists() or not ans.exists():
            continue
        pairs.extend(_load_bfcl_pair(inp, ans, cat))
    if n is not None:
        rng = random.Random(0)
        pairs = rng.sample(pairs, min(n, len(pairs)))

    call_params = {k: v for k, v in bench.get("params", {}).items() if k not in ("categories", "concurrency")}
    concurrency = _concurrency(bench)

    def work(pair):
        item, gt = pair
        tools = _build_tools(item.get("function", []))
        question = _extract_question(item)
        err = None
        if tools:
            try:
                res = runner.client.generate_with_tools(question, tools, **call_params)
                calls = res.get("tool_calls", [])
            except Exception as e:
                calls = []
                err = f"{type(e).__name__}: {e}"
        else:
            try:
                content = runner.client.generate(question, **call_params)
            except Exception as e:
                content = ""
                err = f"{type(e).__name__}: {e}"
            calls = _parse_json_calls(content)
        ok = _score_bfcl(calls, gt)
        rec = {
            "benchmark": "agent_bfcl",
            "dataset": "bfcl",
            "id": item.get("id"),
            "question": question,
            "tools": [t["function"]["name"] for t in tools],
            "tool_calls": [{"name": c.get("name"), "arguments": c.get("arguments")} for c in calls],
            "ground_truth": gt,
            "verdict": ok,
        }
        if err:
            rec["error"] = err
        return rec

    records = _run_pool(work, pairs, concurrency, desc="function_exec")
    correct = sum(1 for r in records if r["verdict"])
    for r in records:
        samples_file.write(json.dumps(r, ensure_ascii=False) + "\n")
    samples_file.flush()
    return {
        "metric": "function_call_accuracy",
        "score": round(correct / len(records), 4) if records else 0.0,
        "n": len(records),
        "total": len(pairs),
    }


def _load_bfcl_pair(inp: Path, ans: Path, cat: str) -> list[tuple[dict, object]]:
    items = [json.loads(l) for l in open(inp, encoding="utf-8") if l.strip()]
    raw_ans = ans.read_text(encoding="utf-8").strip()
    if raw_ans in ("Entry not found", "") or raw_ans.startswith("<ERROR"):
        answers = [None] * len(items)
    else:
        answers = [json.loads(l).get("ground_truth") for l in raw_ans.splitlines() if l.strip()]
    while len(answers) < len(items):
        answers.append(None)
    return list(zip(items, answers))


def _build_tools(funcs: list) -> list[dict]:
    out = []
    for fn in funcs or []:
        params = dict(fn.get("parameters", {}) or {})
        if params.get("type") == "dict":
            params["type"] = "object"
        out.append({"type": "function", "function": {
            "name": fn.get("name", ""),
            "description": fn.get("description", ""),
            "parameters": params,
        }})
    return out


def _extract_question(item: dict) -> str:
    q = item.get("question", [])
    if isinstance(q, list) and q:
        first = q[0]
        if isinstance(first, list) and first:
            return first[0].get("content", "")
        if isinstance(first, dict):
            return first.get("content", "")
    return str(q)


def _parse_json_calls(content: str) -> list[dict]:
    if not content:
        return []
    try:
        obj = json.loads(content)
    except Exception:
        m = re.search(r"\[.*\]", content, re.DOTALL)
        if not m:
            return []
        try:
            obj = json.loads(m.group(0))
        except Exception:
            return []
    if isinstance(obj, dict):
        obj = [obj]
    calls = []
    for o in obj if isinstance(obj, list) else []:
        name = o.get("name") or o.get("function", {}).get("name")
        args = o.get("arguments") or o.get("parameters") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                pass
        if name:
            calls.append({"id": "", "name": name, "arguments": args if isinstance(args, dict) else {}})
    return calls


def _score_bfcl(calls: list[dict], gt) -> bool:
    if gt is None:
        return len(calls) == 0
    if not isinstance(gt, list):
        return False
    expected = []
    for entry in gt:
        if not isinstance(entry, dict):
            return False
        for name, arg_spec in entry.items():
            expected.append((name, arg_spec or {}))
    if len(calls) != len(expected):
        return False
    used = [False] * len(calls)
    for name, arg_spec in expected:
        matched = False
        for i, c in enumerate(calls):
            if used[i]:
                continue
            if c.get("name") == name and _match_args(c.get("arguments", {}), arg_spec):
                used[i] = True
                matched = True
                break
        if not matched:
            return False
    return True


def _match_args(args: dict, spec: dict) -> bool:
    for key, acceptable in (spec or {}).items():
        val = args.get(key, _MISSING)
        if val is _MISSING:
            if isinstance(acceptable, list) and "" in acceptable:
                continue
            return False
        if isinstance(acceptable, list):
            if not any(_eq(val, a) for a in acceptable):
                return False
        else:
            if not _eq(val, acceptable):
                return False
    return True


_MISSING = object()


def _eq(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    return str(a) == str(b)


# ============================ ifeval ============================

def run_ifeval(runner, bench: dict, spec: dict, n, samples_file) -> dict:
    """IFEval 指令遵循逐条校验。strict 为主分，loose 进 outcome 供参照。

    score = Σpassed_instructions / Σtotal_instructions（跨样本所有指令计）。
    """
    from .datasets import load_dataset_samples
    from .ifeval_checker import score_response
    dataset_id = bench["dataset"]
    fields = spec.get("fields", {})
    try:
        samples = load_dataset_samples(dataset_id, runner.datasets_cfg, n=n)
    except Exception as e:
        print(f"[skip] {bench.get('') or bench['dataset']}: 数据集加载失败 — {e}")
        return {"skipped": True, "reason": f"dataset load failed: {type(e).__name__}: {e}"}

    template = bench.get("prompt_template", "raw")
    params = {k: v for k, v in bench.get("params", {}).items() if k != "concurrency"}
    concurrency = _concurrency(bench, default=4)

    def work(sample):
        prompt = _render_raw(template, sample, fields)
        err = None
        try:
            pred = runner.client.generate(prompt, **params)
        except Exception as e:
            pred = ""
            err = f"{type(e).__name__}: {e}"
        instructions = sample.get(fields.get("instructions", "instructions")) or sample.get("instructions") or []
        # 字段映射兼容：HF 真实 IFEval 用 instruction_id_list + kwargs，需重建
        if not instructions and sample.get("instruction_id_list"):
            instructions = _rebuild_hf_instructions(sample)
        strict_res = score_response(pred, instructions, strict=True)
        loose_res = score_response(pred, instructions, strict=False)
        rec = {
            "benchmark": "ifeval_strict",
            "dataset": dataset_id,
            "prompt": prompt,
            "prediction": pred,
            "instructions": [{"id": d["id"]} for d in strict_res["details"]],
            "strict_passed": strict_res["passed"],
            "strict_total": strict_res["total"],
            "strict_pass_rate": (strict_res["passed"] / strict_res["total"]) if strict_res["total"] else 0.0,
            "loose_passed": loose_res["passed"],
            "loose_total": loose_res["total"],
            "verdict": (strict_res["passed"] == strict_res["total"]) if strict_res["total"] else False,
        }
        if err:
            rec["error"] = err
        return rec

    records = _run_pool(work, samples, concurrency, desc="ifeval")
    total_strict = sum(r["strict_total"] for r in records)
    passed_strict = sum(r["strict_passed"] for r in records)
    total_loose = sum(r["loose_total"] for r in records)
    passed_loose = sum(r["loose_passed"] for r in records)
    for r in records:
        samples_file.write(json.dumps(r, ensure_ascii=False) + "\n")
    samples_file.flush()
    score = (passed_strict / total_strict) if total_strict else 0.0
    score_loose = (passed_loose / total_loose) if total_loose else 0.0
    return {
        "metric": "ifeval_strict",
        "score": round(score, 4),
        "score_loose": round(score_loose, 4),
        "n": len(records),
        "total": len(samples),
        "aggregator": "per_instruction",
        "instructions_total": total_strict,
    }


def _render_raw(template: str, sample: dict, fields: dict) -> str:
    if template == "raw":
        return sample.get(fields.get("prompt", "prompt")) or sample.get("prompt") or ""
    # 兜底走 prompts.render
    from .prompts import render
    return render(template, sample)


def _rebuild_hf_instructions(sample: dict) -> list[dict]:
    """HF 真实 IFEval：instruction_id_list + kwargs 重建为 [{instruction_id, kwargs}]。"""
    ids = sample.get("instruction_id_list") or []
    kwargs_list = sample.get("kwargs") or []
    out = []
    for i, iid in enumerate(ids):
        kw = kwargs_list[i] if i < len(kwargs_list) else {}
        out.append({"instruction_id": iid, "kwargs": kw})
    return out
