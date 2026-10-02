# SYNTHETIC growth analytics platform. `make all` runs everything from zero.
PY ?= python
.PHONY: all data sample pipeline model analysis catalog notebook app test lint leakscan clean

all: data pipeline model analysis catalog   ## generate -> pipeline -> model -> analysis -> docs

data:       ## seeded synthetic raw exports (data/raw, git-ignored)
	$(PY) -m src.generate

sample:     ## tiny committed sample of the raw files
	$(PY) -m src.generate --sample data/sample --sample-rows 20

pipeline:   ## raw -> staging -> core -> marts + data-quality checks
	$(PY) -m src.pipeline

model:      ## upgrade-propensity model, scores into fact_user_scores
	$(PY) -m src.model

analysis:   ## analyses, charts, docs/RESULTS.md, docs/MODEL_CARD.md, README key results
	$(PY) -m src.analysis.run_all

catalog:    ## docs/QUERIES.md from SQL headers
	$(PY) -m src.pipeline.catalog

notebook:   ## execute notebooks/analysis.ipynb
	$(PY) scripts/build_notebook.py

app:        ## http://localhost:8050
	$(PY) -m app.main

test:
	$(PY) -m pytest -q

lint:
	ruff check .

leakscan:
	bash scripts/leak_scan.sh

clean:
	rm -rf data/raw data/warehouse models/*.joblib reports/*.json
