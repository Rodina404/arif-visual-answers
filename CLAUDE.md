# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

"Arif Visual Answers": a demo where a user uploads a PDF and asks a question. The answer is a short direct text plus at most 3 typed, grounded visual components (comparison, steps, chart, table, diagram, formula, quiz, flashcards, text). It is Egyptian Arabic (RTL) by default, with an English (LTR) toggle. `README.md` is the original build spec (sections are referenced as §N). `BUILD_LOG.md` records every decision (D1…D18), the live-call log and the known limitations. Read the decisions before changing behaviour.

## Commands

On Windows, run `make` from Git Bash. `uv` and GNU make may not be on PATH: they live in `%APPDATA%/Python/Python313/Scripts` and the WinGet `ezwinports.make` package folder.

- `make setup` — `uv sync`, `npm ci` in `frontend/` and `e2e/`, Playwright Chromium.
- `make serve-mock` — build the frontend and serve everything on :8000 with `MOCK_LLM=1` (no key needed).
- `make test-backend` — pytest. Single test: `cd backend && uv run pytest tests/test_policy.py::test_page_fix_neighbour -q`.
- `make lint` — ruff, mypy, oxlint, `tsc`, the Zod↔Pydantic check (`npm run test:schemas`), and greps for `dangerouslySetInnerHTML` and API keys.
- `make e2e` — Playwright against a fresh mock server (`e2e/helpers/serve.mjs` builds the frontend and wipes `data/e2e`). Single spec: `cd e2e && npx playwright test tests/rtl.spec.ts --project=chromium-ar`. Baselines: `make e2e-update` (OS-specific).
- `make demo` — records `demo/` (video, GIF, key frames).
- Quick UI check against a running :8000: `cd e2e && node helpers/shoot.mjs <ar|en> <q1..q6> <width> <out.png> [compare]`.
- Fixture check: `cd backend && PYTHONPATH=. uv run python scripts/check_fixtures.py`. Page text for writing quotes: `scripts/page_text.py ../fixtures/pdfs/cot.pdf 21`.
- **Live calls** (they cost budget, so ask first): `make test-live`, `make record-fixtures`, `make bench`, `make check-models`, `scripts/diag_gemini.py`.

## Architecture

Request path: `POST /api/ask` → `stream.VisualRun` → provider streams JSON → `parse_partial` (jiter, trailing-strings). `answer_text` deltas become `TEXT_MESSAGE_CONTENT`. Each completed component goes through `policy.ComponentProcessor` (project to type → Pydantic validate → `grounding` → per-type downgrade rules) and then `policy.Selector` (cap of 3, quiz last). The result is emitted as SSE events named after AG-UI events (`docs/protocol.md`). `/api/ask_text` (`TextRun`) is the plain-prose "Before" answer.

- **Catalog**: one source of truth in `backend/app/catalog.py`. `make schema` writes `frontend/src/catalog/schema.json`, which the hand-written Zod in `frontend/src/catalog/schemas.ts` must match (`npm run test:schemas`).
- **`SCHEMA_MODE`** (D5/D18): `json` (default — no API schema; the schema text goes in the cached system prompt), `flat` (one object, no anyOf), `single` (full anyOf), `plan` (plan, then one call per component). Gemini rejected `single` and `flat` with 400 on build day.
- **Grounding** checks against `visible_text` only (excluding chars under 4 pt, white, or off the crop box; hidden text raises `HIDDEN_TEXT_DETECTED`). The quote check is `partial_ratio >= 90` with a ±1 page fix. Numbers must appear in the quote **and** on the page. Digits glued to words (`GSM8K`, `GPT-3`) are not numbers.
- **Providers** (`backend/app/providers/`): `gemini` (Files API, `thinking_level`, never `thinking_budget`), `openai_compat` (self-hosted; sends page-marked text, not the PDF), `mock` (replays `fixtures/answers/<slug>/<qid>.<lang>.json`, chosen by PDF sha256 via `index.json` plus question fuzzy/keyword match). Mock-only headers: `X-Mock-Fixture: dir/name`, `X-No-Cache: 1`.
- **Retries**: 429/503 → 2 backoff retries → `FALLBACK_MODEL`, only before any output has streamed. Timeout keeps the partial text and then sends `RUN_ERROR`.
- **Caches**: parsed PDF pages are memoised per sha256 with a per-hash lock; answers are cached in SQLite (`data/cache.sqlite`), keyed on sha + normalised question + lang + model + prompt version + mode.
- **Frontend** (`frontend/src`): `state/useAnswer.ts` reduces SSE events into slots (planned → ready/dropped); `catalog/registry.tsx` maps types to pure props-in renderers (chart and formula are lazy-loaded). i18n lives in `i18n/` (`useI18n` from `i18n/context`).

## Rules that are easy to break

- Never render model HTML, links or images. No `dangerouslySetInnerHTML` (lint fails); markdown goes through react-markdown with an allowlist and `<` escaped; KaTeX uses `katex.render` into a ref with `trust:false`.
- Fixture quotes must be verbatim from `visible_text` of `cot.pdf`; every `fixtures/answers/cot/q*.json` must stay fully `verified` (`tests/test_fixtures.py`).
- RTL: components set `dir`/`lang` from `props.lang`; use `<bdi>` for mixed tokens and LTR islands for quotes; never apply letter-spacing to Arabic; `sr-only` goes on a wrapper, never on a `<table>`.
- The tool transport decodes backslash escapes (`\u....`, `\t`) in written content. To put a real backslash in source or fixtures, build it with `chr(92)`.
- Live budget: 15 Gemini calls total, 13 used (see BUILD_LOG). Default to `MOCK_LLM=1`.
