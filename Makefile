.PHONY: install demo test list run report clean

install:
	pip install -r requirements.txt
	pip install -e .

demo:
	python scripts/run_benchmark.py run --plan plans/quick/plan.yaml --model mock

list:
	python scripts/run_benchmark.py list

test:
	python -m pytest tests -q

run:
	python scripts/run_benchmark.py run --plan $(PLAN) --model $(MODEL)

report:
	python scripts/generate_report.py --results $(RESULTS) --out $(OUT)

clean:
	rm -rf results/* datasets/**/cache
