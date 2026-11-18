# Development workflow for the DSE Live Analyzer stack.
#
# The default compose command layers docker-compose.local.yml over the main file
# because some Docker runtimes reject the "8001-8002" host port range (single API
# replica on 8001). For the full two-replica stack on a runtime that supports
# ranges, use `make up-full` or override COMPOSE, e.g.:
#   make COMPOSE="docker compose -f docker-compose.yml" up

COMPOSE_FULL ?= docker compose -f docker-compose.yml
COMPOSE      ?= $(COMPOSE_FULL) -f docker-compose.local.yml

SERVICE ?=
SYMBOLS ?=
EMAIL   ?=
ROLE    ?= admin

.DEFAULT_GOAL := help
.PHONY: help build up up-full down restart logs ps migrate shell \
        backfill sync eod create-user set-role \
        test test-backend test-frontend test-e2e

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make <target>\n\nTargets:\n"} \
		/^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

## Docker stack

build: ## Build all images
	$(COMPOSE) build

up: ## Start the stack (detached, rebuild) — single API replica on 8001
	$(COMPOSE) up -d --build

up-full: ## Start the full stack with two API replicas (8001-8002)
	$(COMPOSE_FULL) up -d --build

down: ## Stop and remove containers (keeps the pgdata volume)
	$(COMPOSE) down

restart: ## Restart all containers without rebuilding
	$(COMPOSE) restart

logs: ## Follow logs (SERVICE=api to filter)
	$(COMPOSE) logs -f $(SERVICE)

ps: ## Show container status
	$(COMPOSE) ps

migrate: ## Apply database migrations (normally run automatically on `up`)
	$(COMPOSE) run --rm migrate

shell: ## Open a shell in the worker container
	$(COMPOSE) exec worker sh

## Operator CLI (runs inside the worker container)

backfill: ## Backfill history for all instruments, or SYMBOLS="GP BATBC"
	$(COMPOSE) exec worker python -m dse.cli backfill $(SYMBOLS)

sync: ## Sync instruments now, e.g. SYMBOLS="GP BATBC"
	@test -n "$(SYMBOLS)" || (echo "usage: make sync SYMBOLS=\"GP BATBC\""; exit 1)
	$(COMPOSE) exec worker python -m dse.cli sync $(SYMBOLS)

eod: ## Append today's bars from one post-close snapshot
	$(COMPOSE) exec worker python -m dse.cli eod

create-user: ## Create an account: make create-user EMAIL=you@example.com ROLE=admin
	@test -n "$(EMAIL)" || (echo "usage: make create-user EMAIL=you@example.com [ROLE=admin]"; exit 1)
	$(COMPOSE) exec worker python -m dse.cli create-user $(EMAIL) --role $(ROLE)

set-role: ## Change a role: make set-role EMAIL=you@example.com ROLE=admin
	@test -n "$(EMAIL)" || (echo "usage: make set-role EMAIL=you@example.com ROLE=admin"; exit 1)
	$(COMPOSE) exec worker python -m dse.cli set-role $(EMAIL) $(ROLE)

## Tests

test: test-backend test-frontend ## Run backend and frontend checks

test-backend: ## Lint, type-check and unit-test the backend
	cd backend && ruff check . && ruff format --check . && mypy && lint-imports && pytest

test-frontend: ## Lint, type-check and unit-test the frontend
	cd frontend && npm run check

test-e2e: ## Run Playwright end-to-end tests (requires the running stack)
	cd frontend && npm run e2e
