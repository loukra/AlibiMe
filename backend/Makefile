VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: venv install env test api worker seed migrate revision fmt clean

venv:
	python3.11 -m venv $(VENV)
	$(PIP) install --upgrade pip

install: venv
	$(PIP) install -e ".[dev]"

env:
	test -f .env || cp .env.example .env

test:
	$(PY) -m pytest

api: env
	$(VENV)/bin/uvicorn app.main:app --reload --port 8000

worker: env
	$(PY) -m app.workers.run

seed: env
	$(PY) -m app.seeds.seed

migrate: env
	$(VENV)/bin/alembic upgrade head

revision:
	$(VENV)/bin/alembic revision --autogenerate -m "$(m)"

clean:
	rm -f believablecall.db
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
