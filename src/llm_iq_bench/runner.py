from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
from pathlib import Path

import yaml

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(it, *_a, **_k):
        return it

from .config import load_models, load_datasets, load_benchmarks, load_suite, load_plan
from .models import build_model_client, _mask_key
from .datasets import load_dataset_samples
from .metrics import compute_metric, aggregate_multisample, _boxed, _last_number
from .prompts import render
from . import executors

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "results"

_NOT_IMPLEMENTED_RUNNERS = {"swe_docker", "agent_loop"}


def _git_info() -> dict:
    """返回 {commit, dirty, branch}；git 不可用时任一字段为 None，不抛。"""
    def _run(*args):
        try:
            r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=4)
            if r.returncode != 0:
                return None
            return r.stdout.strip() or None
        except Exception:
            return None
    commit = _run("git", "rev-parse", "HEAD")
    branch = _run("git", "rev-parse", "--abbrev-ref", "HEAD")
    dirty = None
    s = _run("git", "status", "--porcelain")
    if s is not None:
        dirty = bool(s)
    return {"commit": commit, "dirty": dirty, "branch": branch}


def _default_seed(plan_name: str) -> int:
    """无显式 seed 时按 plan 名哈希取稳定值。"""
    h = hashlib.md5(plan_name.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % 1_000_000


def _gold_from(spec: dict, sample: dict):
    field = spec.get("fields", {}).get("gold")
    if field and field in sample:
        return sample[field]
    if "gold" in sample:
        return sample["gold"]
    return None


def _answer_extractor(pred: str, kind: str | None) -> str:
    if kind == "last_number":
        m = re.findall(r"-?\d+\.?\d*", pred.replace(",", ""))
        return m[-1] if m else pred
    if kind == "boxed":
        b = _boxed(pred)
        return b if b is not None else pred
    return pred


class Runner:
    def __init__(self, model_id: str, models_cfg: dict | None = None,
                 datasets_cfg: dict | None = None, benchmarks_cfg: dict | None = None,
                 seed: int | None = None):
        self.model_id = model_id
        self.models_cfg = models_cfg or load_models()
        self.datasets_cfg = datasets_cfg or load_datasets()
        self.benchmarks_cfg = benchmarks_cfg or load_benchmarks()
        self.seed = seed
        self.client = build_model_client(model_id, self.models_cfg, seed=seed)
        self._last_run_dir: Path | None = None

    def run_plan(self, plan_path: str | Path, max_per_task: int | None = None,
                 seed: int | None = None) -> dict:
        plan = load_plan(plan_path)
        model_id = plan.get("model", self.model_id)
        if model_id != self.model_id or seed is not None:
            self.model_id = model_id
            self.seed = seed if seed is not None else self.seed
            self.client = build_model_client(model_id, self.models_cfg, seed=self.seed)

        # seed 解析：CLI > plan > default_seed(plan_name)
        if self.seed is None:
            self.seed = plan.get("seed")
        if self.seed is None:
            self.seed = _default_seed(plan.get("name", "plan"))
        self.client.seed = self.seed

        timestamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
        run_dir = RESULTS_DIR / f"{plan['name']}_{model_id}_{timestamp}"
        samples_path = run_dir / "samples.jsonl"
        summary_path = run_dir / "summary.json"
        run_dir.mkdir(parents=True, exist_ok=True)
        self._last_run_dir = run_dir

        # P0-3：executors seed 注入 —— 给每个 task 的 bench.params 补 seed（若未设）
        for entry in plan["tasks"]:
            bid = entry["benchmark"]
            bcfg = self.benchmarks_cfg.get(bid, {})
            params = bcfg.setdefault("params", {})
            if "seed" not in params:
                params["seed"] = self.seed

        results = {}
        samples_file = open(samples_path, "w", encoding="utf-8")

        for entry in plan["tasks"]:
            bench_id = entry["benchmark"]
            n = entry.get("n", max_per_task)
            outcome = self._run_one(bench_id, n, samples_file)
            results[bench_id] = outcome

        samples_file.close()
        summary = {
            "plan": plan["name"],
            "model": model_id,
            "timestamp": timestamp,
            "seed": self.seed,
            "tasks": results,
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        # P0-3：写 config_snapshot.yaml（冻结配置）
        self._write_config_snapshot(run_dir, plan, model_id, timestamp)

        print(f"\n结果已写入: {run_dir}")

        try:
            from .reporter import emit_run_report
            md_path = emit_run_report(summary, run_dir, tag=plan.get("tag"))
            print(f"报告已生成: {md_path.relative_to(ROOT)}  (tracked, 供对比)")
        except Exception as e:
            print(f"[warn] 报告生成失败: {e}")

        self._print_summary(summary)
        return summary

    def _write_config_snapshot(self, run_dir: Path, plan: dict, model_id: str, timestamp: str):
        involved_datasets = set()
        involved_benchmarks = {}
        for entry in plan["tasks"]:
            bid = entry["benchmark"]
            bcfg = self.benchmarks_cfg.get(bid, {})
            involved_benchmarks[bid] = bcfg
            ds = bcfg.get("dataset")
            if ds:
                involved_datasets.add(ds)
        model_entry = dict(self.models_cfg.get(model_id, {}))
        if "api_key" in model_entry:
            model_entry["api_key"] = _mask_key(model_entry.get("api_key", ""))
        else:
            # 也可能从 build 时展开；记脱敏占位
            model_entry["api_key"] = _mask_key(self.client.api_key)
        snapshot = {
            "plan": plan,
            "model": {model_id: model_entry},
            "datasets": {d: self.datasets_cfg.get(d, {}) for d in sorted(involved_datasets)},
            "benchmarks": involved_benchmarks,
            "git": _git_info(),
            "seed": self.seed,
            "timestamp": timestamp,
            "runner_version": __import__("llm_iq_bench", fromlist=["__version__"]).__version__,
        }
        (run_dir / "config_snapshot.yaml").write_text(
            yaml.safe_dump(snapshot, allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )

    def _run_one(self, bench_id: str, n: int | None, samples_file) -> dict:
        bench = self.benchmarks_cfg[bench_id]
        dataset_id = bench["dataset"]
        spec = self.datasets_cfg[dataset_id]
        runner_kind = bench.get("runner")
        if runner_kind in _NOT_IMPLEMENTED_RUNNERS:
            print(f"[skip] {bench_id}: 需专用 runner ({runner_kind})，见 scripts/ — 骨架阶段跳过")
            return {"skipped": True, "reason": f"runner {runner_kind} not implemented"}
        if runner_kind:
            outcome = executors.dispatch(runner_kind, self, bench, spec, n, samples_file)
            if "score" in outcome:
                outcome["benchmark"] = bench_id
            return outcome

        n = n or spec.get("n_default", 200)
        metric = bench["metric"]

        # P0-2：metric 未实现探针 —— 先于数据集加载，避免 NotImplementedError 任务被误报 0 分
        try:
            compute_metric(metric, "", None)
        except NotImplementedError:
            print(f"[errored] {bench_id}: metric `{metric}` 未实现")
            return {"errored": True, "reason": f"metric not implemented: {metric}"}
        except Exception:
            pass  # 其它异常（如 gold 校验）不影响真实跑分

        try:
            samples = load_dataset_samples(dataset_id, self.datasets_cfg, n=n)
        except Exception as e:
            print(f"[skip] {bench_id}: 数据集加载失败 — {e}")
            return {"skipped": True, "reason": f"dataset load failed: {type(e).__name__}: {e}"}

        template = bench.get("prompt_template", "raw")
        extractor = bench.get("answer_extractor")
        gold_extractor = bench.get("gold_extractor")  # P1: gold 为长文本时单独提取（默认 None=不提取）
        params = dict(bench.get("params", {}))
        n_samples = params.pop("n", None)
        multisample = bool(n_samples and n_samples > 1)
        aggregator = bench.get("aggregator") if multisample else None
        # A2: aggregator 支持 str 或 list[str]（双报）。统一转 list 处理。
        if multisample:
            aggregators = [aggregator] if isinstance(aggregator, str) else list(aggregator or [])
            primary_agg = aggregators[0] if aggregators else None
            corrects = {a: 0 for a in aggregators}
            scoreds = {a: 0 for a in aggregators}
        else:
            aggregators = []
            primary_agg = None

        correct = 0
        scored = 0
        for sample in tqdm(samples, desc=bench_id, disable=False):
            prompt = render(template, sample)
            ctx = {"choices": sample.get("choices", []),
                   "query_type": sample.get("type")}
            gold = sample.get("gold") if "gold" in sample else _gold_from(spec, sample)
            if isinstance(gold, str) and gold_extractor:
                gold = _answer_extractor(gold, gold_extractor)

            if multisample:
                preds = self.client.generate_n(prompt, int(n_samples), **params)
                verdicts = {}
                for agg in aggregators:
                    try:
                        v = aggregate_multisample(agg, preds, gold, extractor, metric, **ctx)
                    except NotImplementedError:
                        v = None
                    verdicts[agg] = v
                    if v is not None:
                        scoreds[agg] += 1
                        if v:
                            corrects[agg] += 1
                # primary 累计（向后兼容旧 correct/scored 字段）
                primary_v = verdicts.get(primary_agg)
                if primary_v is not None:
                    scored += 1
                    if primary_v:
                        correct += 1
                samples_file.write(json.dumps({
                    "benchmark": bench_id,
                    "dataset": dataset_id,
                    "prompt": prompt,
                    "n_predictions": preds,
                    "aggregator": aggregator,
                    "aggregators": aggregators,
                    "gold": gold,
                    "verdict": primary_v,
                    "verdicts": verdicts,
                }, ensure_ascii=False) + "\n")
                samples_file.flush()
                continue

            pred = self.client.generate(prompt, **params)
            pred_ans = _answer_extractor(pred, extractor)
            try:
                verdict = compute_metric(metric, pred_ans, gold, **ctx)
            except NotImplementedError:
                verdict = None

            if verdict is not None:
                scored += 1
                if isinstance(verdict, bool) and verdict:
                    correct += 1
                elif isinstance(verdict, (int, float)):
                    correct += float(verdict)

            samples_file.write(json.dumps({
                "benchmark": bench_id,
                "dataset": dataset_id,
                "prompt": prompt,
                "prediction": pred,
                "gold": gold,
                "verdict": verdict,
            }, ensure_ascii=False) + "\n")
            samples_file.flush()

        score = correct / scored if scored else 0.0
        result = {"metric": metric, "score": round(score, 4), "n": scored, "total": len(samples)}
        if multisample:
            result["aggregator"] = aggregator
            result["n_samples"] = int(n_samples)
            # A2: 多 aggregator 时输出各 aggregator 独立 score（双报）
            if len(aggregators) > 1:
                result["aggregators"] = {
                    a: round(corrects[a] / scoreds[a], 4) if scoreds[a] else 0.0
                    for a in aggregators
                }
                result["n_per_aggregator"] = {a: scoreds[a] for a in aggregators}
        return result

    def _print_summary(self, summary: dict):
        print("\n=== Summary ===")
        print(f"plan={summary['plan']} model={summary['model']} seed={summary.get('seed')}")
        for bid, r in summary["tasks"].items():
            if r.get("skipped"):
                print(f"  {bid:24s} SKIPPED ({r['reason']})")
            elif r.get("errored"):
                print(f"  {bid:24s} ERRORED ({r['reason']})")
            else:
                print(f"  {bid:24s} {r['score']:.3f}  (n={r['n']})")
