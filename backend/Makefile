VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: venv install env test api worker seed migrate revision fmt clean cli demo \
        bootstrap setup start

venv:
	python3.11 -m venv $(VENV)
	$(PIP) install --upgrade pip

install: venv
	$(PIP) install -e ".[dev,tui]"

env:
	test -f .env || cp .env.example .env

# First-time, from-scratch setup: deps + config + database + seed data.
bootstrap: install env migrate seed
	@echo ""
	@echo "✅ Bootstrap complete."
	@echo "   Start the API:   make start    (configures the DB, then serves on :8000)"
	@echo "   Launch the app:  make app      (in a second terminal)"

# Configure the database (idempotent) without reinstalling deps.
setup: env migrate seed

# Configure + start the API in one command.
start: setup
	$(VENV)/bin/uvicorn app.main:app --reload --port 8000

test:
	$(PY) -m pytest

api: env
	$(VENV)/bin/uvicorn app.main:app --reload --port 8000

worker: env
	$(PY) -m app.workers.run

seed: env
	$(PY) -m app.seeds.seed

# CLI: pass args via `make cli args="templates"` or run the script directly.
cli:
	$(PY) scripts/cli.py $(args)

demo:
	$(PY) scripts/cli.py demo

# Interactive TUI "app" (arrow-key menus, schedule + receive a call).
app:
	$(PY) scripts/app.py

# Open the TUI in a brand-new macOS Terminal window.
app-window:
	osascript -e 'tell application "Terminal" to do script "cd \"$(CURDIR)\" && .venv/bin/python scripts/app.py"' \
	          -e 'tell application "Terminal" to activate'

migrate: env
	$(VENV)/bin/alembic upgrade head

revision:
	$(VENV)/bin/alembic revision --autogenerate -m "$(m)"

clean:
	rm -f believablecall.db
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
