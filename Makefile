.PHONY: install demo test list run report compare clean

install:
	pip install -r requirements.txt
	pip install -e .

demo:
	python scripts/run_benchmark.py run --plan plans/quick/plan.yaml --model mock

list:
	python scripts/run_benchmark.py list

test:
	python3 -m pytest tests -q 2>/dev/null || python3 tests/_runner.py

test-py:
	python3 -m pytest tests -q

test-py3:
	python3 tests/_runner.py

run:
	python scripts/run_benchmark.py run --plan $(PLAN) --model $(MODEL)

report:
	python scripts/generate_report.py --results $(RESULTS) --out $(OUT)

compare:
	python scripts/compare_reports.py

clean:
	rm -rf results/* datasets/**/cache
