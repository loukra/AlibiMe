VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: venv install env test api api-lan worker seed migrate revision fmt clean cli demo \
        bootstrap setup start sync-senders sync-senders-vapi eval

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

# Serve on all interfaces so a physical iPhone on the same Wi-Fi can reach it.
# Point the app at the printed URL via the BC_BACKEND_URL scheme env var.
api-lan: env
	@ip=$$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null); \
	echo "Serving on http://$$ip:8000  -> set BC_BACKEND_URL to this in the Xcode scheme"
	$(VENV)/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

worker: env
	$(PY) -m app.workers.run

seed: env
	$(PY) -m app.seeds.seed

# Mirror Twilio's number inventory into the local sender-line pool. Run after
# adding/removing/rotating Twilio numbers (requires Twilio creds in .env).
sync-senders: env
	$(PY) -m app.admin.sync_sender_lines

# Same, then import the voice-capable lines into Vapi and store their ids.
sync-senders-vapi: env
	$(PY) -m app.admin.sync_sender_lines --vapi

# Voice-agent evals. Offline by default; EVAL_LLM_PROVIDER=openai (or anthropic)
# talks to the real model, args="--judge" adds the LLM judge.
eval:
	$(PY) -m evals.run $(args)

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
