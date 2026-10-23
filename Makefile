COMPOSE := docker compose
RUN := $(COMPOSE) run --rm api python -m

.PHONY: up down logs ingest backfill metrics fundamentals export-data import-data test lint dev-api dev-web

up:            ## Start db, api, scheduler and web
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f api scheduler

ingest:        ## Load stock list, latest bhavcopy and compute metrics
	$(RUN) app.ingest.equity_list
	$(RUN) app.ingest.bhavcopy
	$(RUN) app.ingest.compute_metrics

backfill:      ## make backfill FROM=2024-01-01 (one request per trading day, ~1.5s apart)
	$(RUN) app.ingest.bhavcopy --from $(FROM) --skip-existing
	$(RUN) app.ingest.compute_metrics

metrics:
	$(RUN) app.ingest.compute_metrics

fundamentals:  ## make fundamentals FILE=data/my_fundamentals.csv
	$(COMPOSE) run --rm -v $(PWD)/data:/app/data api python -m app.ingest.fundamentals_csv $(FILE)
	$(RUN) app.ingest.compute_metrics

export-data:   ## Dump all tables to data/export/*.csv.gz (SINCE=2021-01-01 for recent prices only)
	SINCE='$(SINCE)' scripts/export_data.sh

import-data:   ## make import-data TARGET_URL='postgresql://...'  (replaces table contents)
	TARGET_URL='$(TARGET_URL)' scripts/import_data.sh

test:
	cd backend && python -m pytest -q

lint:
	cd backend && ruff check app tests
	cd web && npm run typecheck

dev-api:       ## Run API locally with hot reload (needs db from `make up` or local Postgres)
	cd backend && uvicorn app.main:app --reload

dev-web:
	cd web && npm run dev
