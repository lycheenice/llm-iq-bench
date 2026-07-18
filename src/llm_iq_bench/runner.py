from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(it, *_a, **_k):
        return it

from .config import load_models, load_datasets, load_benchmarks, load_suite, load_plan
from .models import build_model_client
from .datasets import load_dataset_samples
from .metrics import compute_metric
from .prompts import render
from . import executors

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "results"

_NOT_IMPLEMENTED_RUNNERS = {"swe_docker", "agent_loop"}


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
        m = re.findall(r"\\boxed\{([^}]*)\}", pred)
        return m[-1].strip() if m else pred
    return pred


class Runner:
    def __init__(self, model_id: str, models_cfg: dict | None = None,
                 datasets_cfg: dict | None = None, benchmarks_cfg: dict | None = None):
        self.model_id = model_id
        self.models_cfg = models_cfg or load_models()
        self.datasets_cfg = datasets_cfg or load_datasets()
        self.benchmarks_cfg = benchmarks_cfg or load_benchmarks()
        self.client = build_model_client(model_id, self.models_cfg)

    def run_plan(self, plan_path: str | Path, max_per_task: int | None = None) -> dict:
        plan = load_plan(plan_path)
        model_id = plan.get("model", self.model_id)
        if model_id != self.model_id:
            self.model_id = model_id
            self.client = build_model_client(model_id, self.models_cfg)

        timestamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
        run_dir = RESULTS_DIR / f"{plan['name']}_{model_id}_{timestamp}"
        samples_path = run_dir / "samples.jsonl"
        summary_path = run_dir / "summary.json"
        run_dir.mkdir(parents=True, exist_ok=True)

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
            "tasks": results,
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\n结果已写入: {run_dir}")

        try:
            from .reporter import emit_run_report
            md_path = emit_run_report(summary, run_dir, tag=plan.get("tag"))
            print(f"报告已生成: {md_path.relative_to(ROOT)}  (tracked, 供对比)")
        except Exception as e:
            print(f"[warn] 报告生成失败: {e}")

        self._print_summary(summary)
        return summary

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
        try:
            samples = load_dataset_samples(dataset_id, self.datasets_cfg, n=n)
        except Exception as e:
            print(f"[skip] {bench_id}: 数据集加载失败 — {e}")
            return {"skipped": True, "reason": f"dataset load failed: {type(e).__name__}: {e}"}
        metric = bench["metric"]
        template = bench.get("prompt_template", "raw")
        extractor = bench.get("answer_extractor")
        params = bench.get("params", {})

        correct = 0
        scored = 0
        for sample in tqdm(samples, desc=bench_id, disable=False):
            prompt = render(template, sample)
            pred = self.client.generate(prompt, **params)
            pred_ans = _answer_extractor(pred, extractor)
            ctx = {"choices": sample.get("choices", []),
                   "query_type": sample.get("type")}
            try:
                verdict = compute_metric(metric, pred_ans, sample.get("gold") if "gold" in sample else _gold_from(spec, sample), **ctx)
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
                "gold": sample.get("gold") or _gold_from(spec, sample),
                "verdict": verdict,
            }, ensure_ascii=False) + "\n")
            samples_file.flush()

        score = correct / scored if scored else 0.0
        return {"metric": metric, "score": round(score, 4), "n": scored, "total": len(samples)}

    def _print_summary(self, summary: dict):
        print("\n=== Summary ===")
        print(f"plan={summary['plan']} model={summary['model']}")
        for bid, r in summary["tasks"].items():
            if r.get("skipped"):
                print(f"  {bid:24s} SKIPPED ({r['reason']})")
            else:
                print(f"  {bid:24s} {r['score']:.3f}  (n={r['n']})")
