# Run from Git Bash (or any POSIX sh) on Windows.
SHELL := sh
UV ?= uv
export PYTHONUTF8 := 1

.PHONY: setup dev build serve serve-mock test-backend lint e2e e2e-update test-live record-fixtures demo bench check-models schema fixtures-pdfs

setup:
	cd backend && $(UV) sync
	cd frontend && (npm ci || npm install)
	cd e2e && (npm ci || npm install) && npx playwright install chromium

dev:
	(cd backend && $(UV) run uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npx vite --port 5173) & \
	wait

build:
	cd frontend && npm run build

# The real product: live model from PROVIDER in .env (groq | gemini), any PDF. MOCK_LLM is forced off.
serve: build
	cd backend && MOCK_LLM=0 $(UV) run uvicorn app.main:app --port 8000

# Deterministic replay of prepared fixtures, for tests and offline demos only.
serve-mock: build
	cd backend && MOCK_LLM=1 $(UV) run uvicorn app.main:app --port 8000

test-backend:
	cd backend && $(UV) run pytest -q

schema:
	cd backend && $(UV) run python scripts/export_schema.py

fixtures-pdfs:
	cd backend && $(UV) run python scripts/make_injection_pdf.py

lint:
	cd backend && $(UV) run ruff check . && $(UV) run mypy app --ignore-missing-imports
	cd frontend && npm run lint && npm run typecheck
	cd frontend && npm run test:schemas
	@if grep -rn "dangerouslySetInnerHTML" frontend/src; then echo "dangerouslySetInnerHTML is forbidden"; exit 1; fi
	@if [ -d frontend/dist ] && grep -rEl "AIza[0-9A-Za-z_-]{20,}" frontend/dist; then echo "API key pattern in dist"; exit 1; fi

e2e:
	cd e2e && npx playwright test --grep-invert "@live|@demo"

e2e-update:
	cd e2e && npx playwright test --grep-invert "@live|@demo" --update-snapshots

test-live:
	cd e2e && LIVE=1 npx playwright test --grep @live --project=chromium-ar --workers=1

record-fixtures:
	cd backend && $(UV) run python scripts/record_fixtures.py

demo:
	cd e2e && MOCK_TTFT_MS=900 npx playwright test --grep @demo --project=demo
	ffmpeg -y -i demo/arif-visual-answers.webm -vf "fps=12,scale=960:-1:flags=lanczos" demo/arif-visual-answers.gif

bench:
	cd backend && $(UV) run python scripts/bench.py

check-models:
	cd backend && $(UV) run python scripts/check_models.py
