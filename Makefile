.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help run stop test pycompile jscheck lint data verify clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

run: ## Start the app (FastAPI preferred, stdlib fallback)
	./run.sh

stop: ## Stop the app
	./stop.sh

test: pycompile jscheck ## Run the full validation suite
	pytest -q

pycompile: ## Byte-compile all Python sources
	python - <<'PY'
import compileall, sys
ok = True
for d in ('app', 'engines', 'tests'):
    ok = compileall.compile_dir(d, quiet=1) and ok
sys.exit(0 if ok else 1)
PY

jscheck: ## Syntax-check the frontend bundle
	node --check web/js/app.bundle.js

data: ## Fetch large datasets that are not committed
	bash scripts/fetch_data.sh

verify: ## Verify committed data checksums against manifests
	python scripts/verify_manifests.py

clean: ## Remove runtime artefacts
	rm -rf .pytest_cache __pycache__ app/__pycache__ engines/__pycache__ tests/__pycache__ data/cache gridiq.log gridiq.pid
