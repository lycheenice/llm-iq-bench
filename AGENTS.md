# AGENTS.md

`llm-iq-bench` — YAML-driven multi-dimensional LLM capability benchmark framework. Python ≥3.10; `pyyaml` + `requests` are the only hard dependencies (`datasets`/`tqdm`/`pytest`/`openai` are optional — `models.py` talks HTTP directly via `requests`, no `openai` lib). Docs, comments, and config are largely in Chinese; prompts/metrics are English — keep that style.

## Commands (exact forms — easy to get wrong)

```bash
make install                          # pip install -r requirements.txt && pip install -e .
make demo                             # plans/quick + mock model: zero API key, zero dataset, offline
python scripts/run_benchmark.py list  # list models / datasets / benchmarks / dimensions
python scripts/run_benchmark.py run --plan plans/quick/plan.yaml --model mock
python scripts/run_benchmark.py run --plan plans/local_v1/plan.yaml --model glm-local  # 本机 GLM 评测
python -m pytest tests -q             # 15 smoke tests
make run   PLAN=plans/reasoning_deep/plan.yaml MODEL=gpt-4o   # Makefile `run` REQUIRES PLAN + MODEL vars
make report RESULTS=results/<run_dir> OUT=reports/x.md        # `report` REQUIRES RESULTS + OUT vars
make clean                            # WARNING: rm -rf results/* and datasets/**/cache
```

No `PYTHONPATH=src` is needed — `scripts/*.py` and `tests/test_smoke.py` insert `src/` into `sys.path` themselves. After `make install`, the `llm-iq-bench` console entry point (`pyproject.toml`) is also available.

## Data flow (config-driven, not code-driven)

`plan.yaml` → `Runner.run_plan()` iterates `tasks[].benchmark` ids → each id resolves via `configs/benchmarks.yaml` (`dataset` + `metric` + `prompt_template` + `runner` + `params`) → `configs/datasets.yaml` spec → `ModelClient.generate()` → `metrics.compute_metric()` → writes `results/<plan>_<model>_<timestamp>/{samples.jsonl,summary.json}`.

- **Suites are informational; plans drive execution.** `suites/<dim>/definition.yaml` describes a dimension but is NOT what runs — the `benchmark` ids listed in a plan are. The suite↔benchmark mapping is hardcoded in `cli.py:SUITE_TASK_DIR`.
- Extension (new dataset / dimension / model / plan / metric / provider) follows the table in `docs/architecture.md`; no core changes. A new metric must be registered in the `METRICS` dict in `src/llm_iq_bench/metrics.py`.

## Critical gotchas

- **Some benchmarks are still stubbed and silently SKIPPED, not broken.** `runner.py:_NOT_IMPLEMENTED_RUNNERS = {swe_docker, agent_loop}` → those tasks print `[skip]` and return `{"skipped": true}`. The other three runners — `code_exec`, `needle_gen`, `function_exec` — ARE implemented in `src/llm_iq_bench/executors.py` (sandboxed Python execution, needle-in-haystack generator, BFCL tool-call scoring). Metrics `pass_at_1`/`function_call_accuracy` for those are computed inside the executors, NOT via `metrics.py` (which still raises `NotImplementedError` — that path is bypassed). To enable a remaining runner, implement it in `executors.py` AND add a dispatch branch, AND remove it from `_NOT_IMPLEMENTED_RUNNERS`. Do not "fix" a skip by just deleting it from the set.
- **Datasets are stored under `/data1/datasets`, NOT vendored in repo.** `humaneval` (jsonl.gz from GitHub), `mbpp` (jsonl from GitHub), `bfcl` (JSONL from `gorilla-llm/Berkeley-Function-Calling-Leaderboard`) point there via absolute `repo:` paths in `configs/datasets.yaml`. `needle` is generated in-memory by the executor (no file). `source: builtin` (`demo_mc`/`demo_qa`) is the offline demo path. If `/data1/datasets` is missing, re-download (see `datasets/README.md`); note `huggingface.co` is unreachable in this env — use the **`hf-mirror.com`** mirror with `curl -L` (follows the LFS redirect).
- **Optional imports degrade gracefully** — `list` and `run --model mock` work in a minimal pyyaml+requests env. HF / openai paths only fail when first used; `models.py` needs NO `openai` lib (pure `requests`).

## Non-obvious conventions

- **A plan's `model:` field overrides `--model`.** `runner.py:run_plan` rebuilds the client from the plan's model if present; the CLI `--model` is only a fallback default. Change the model in the plan YAML to control what runs.
- **Per-model `base_url` / `api_key_env` ARE wired into the client** (`models.py:build_model_client`). Use `api_model_id` when the config key differs from the API model name (e.g. `glm-local` → `api_model_id: glm`). Local providers (localhost/127.0.0.1) default `api_key` to `"EMPTY"` when the env var is unset. `config.py` still expands `${VAR:default}` in YAML for the openai-cloud models.
- **GLM-5.2 (`glm-local`) is a reasoning model.** It emits chain-of-thought in `reasoning_content` and burns `reasoning_tokens` against `max_tokens`, so small `max_tokens` (e.g. 64) truncates before any answer. The executors set `max_tokens` ≥ 512–2048 accordingly. `models.py:_choice_content` falls back to `reasoning_content` when `content` is empty.
- **`answer_extractor`** (`last_number` / `boxed`) is applied in `runner._answer_extractor` before the metric — it is separate from metric logic, not registered in `metrics.py`.
- **Scoring conventions must stay in sync** between `suites/<dim>/definition.yaml` and `skills/<dim>-testing.md` — change both together (see `skills/README.md`).
- `reasoning_aime` uses `temperature: 0.7, n: 4` (multi-sample pass@k); nearly all other tasks use `temperature: 0`.

## Repo state

- **No git repo, no CI** (not `git init`'d as of `docs/devlog.md` 2026-07-18). There are no branch / PR / release conventions yet. `docs/devlog.md` is the running progress log + P0–P3 backlog (read it before large changes).
- Gitignored: `results/`, `reports/*.md` (except `template.md` and `README.md`), `datasets/**/cache/`, raw dataset files (`.parquet`/`.jsonl`/`.zip`), `.env`, `*.log`.
