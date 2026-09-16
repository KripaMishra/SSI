# Commands for running SSI. Dependencies come from pyproject.toml through uv.
ARGS ?=
PORT ?= 8000

.DEFAULT_GOAL := help
.PHONY: help sync api api-dev worker test up down

help: ## list the commands
	@grep -E '^[a-z][a-z-]*:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-9s %s\n", $$1, $$2}'

sync: ## install or update dependencies from uv.lock
	uv sync --frozen

api: ## API server on 0.0.0.0:8000 (add PORT=8099 to change)
	uv run uvicorn src.api.main:app --host 0.0.0.0 --port $(PORT)

api-dev: ## API server on 127.0.0.1:8000 with auto-reload
	uv run uvicorn src.api.main:app --reload --port $(PORT)

worker: ## queue worker for the "asks" queue (ARGS="-p 4" for more processes)
	uv run dramatiq src.queue.actors -Q asks -t 8 $(ARGS)

test: ## run the test suite
	uv run python -m unittest discover -s tests

up: ## start redis, api and worker in containers
	docker compose up --build

down: ## stop the containers
	docker compose down
