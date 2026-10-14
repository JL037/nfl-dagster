# Everyday commands. NFL_ENV picks the warehouse environment (dev -> NFL_DEV, prod -> NFL).
# Each environment also gets its own Dagster home (run history never mixes), its own code
# location name (shown on every page of the UI), and its own port:
#   dev  -> nfl_dagster_dev  on http://localhost:3000
#   prod -> nfl_dagster_prod on http://localhost:3001
# Uses the project's virtual environment, so no need to activate it first.

export PATH := $(CURDIR)/.venv/bin:$(PATH)
DAGSTER_HOME_DEV  := $(CURDIR)/.dagster_home/dev
DAGSTER_HOME_PROD := $(CURDIR)/.dagster_home/prod

.PHONY: help dev prod clone-dev parse validate test

help:  ## List commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

dev:  ## Dagster UI against NFL_DEV, http://localhost:3000 (day-to-day work)
	@mkdir -p $(DAGSTER_HOME_DEV) && touch $(DAGSTER_HOME_DEV)/dagster.yaml
	NFL_ENV=dev DAGSTER_HOME=$(DAGSTER_HOME_DEV) dagster dev -w workspaces/dev.yaml -p 3000

prod:  ## Dagster UI against NFL, http://localhost:3001 (production; main only)
	@if [ "$$(git rev-parse --abbrev-ref HEAD)" != "main" ]; then \
		echo "Refusing to run prod from branch '$$(git rev-parse --abbrev-ref HEAD)'. Merge to main first."; exit 1; fi
	@mkdir -p $(DAGSTER_HOME_PROD) && touch $(DAGSTER_HOME_PROD)/dagster.yaml
	NFL_ENV=prod DAGSTER_HOME=$(DAGSTER_HOME_PROD) dagster dev -w workspaces/prod.yaml -p 3001

clone-dev:  ## Recreate NFL_DEV as a zero-copy clone of NFL
	python scripts/clone_dev.py

parse:  ## Build the dbt manifest
	cd dbt_project && dbt parse

validate: parse  ## Check that the Dagster definitions load
	dagster definitions validate

test: parse  ## Run the test suite
	pytest
