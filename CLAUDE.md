# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

This repo is **spec-first**. At the time of writing it holds only `README.md` (the full build brief for "Arif Visual Answers") and `.env` (which contains `GEMINI_API_KEY`). It is not yet a git repo. No code exists. `README.md` is the source of truth: work through its phases (§14) in order, tick its checkboxes, record every decision, version and live-call count in `BUILD_LOG.md`, and commit after each phase (`git commit -m "phase N: <summary>"`).

Before the first commit, make sure `.gitignore` covers `.env`, `data/`, `.venv`, `node_modules`, `test-results` and `playwright-report`. Never print or log the key value.

## What is being built

This is a demo prototype for Arif, the Arabic-first assistant in Qriib. Given an uploaded PDF and a question, it returns a short direct answer plus **at most 3 typed visual components** (chart, comparison, steps, table, diagram, formula, quiz, flashcards, text). Every component is grounded with a page number and a verbatim quote, the output is safe because the model emits data and never HTML, Egyptian Arabic (RTL) is the default with an English (LTR) toggle, and each answer reports its tokens, USD cost and latency. The demo PDF is the Chain-of-Thought paper (arXiv 2201.11903), stored at `fixtures/pdfs/cot.pdf`.

## Stack

- Backend: Python 3.12, FastAPI, `uv`, `google-genai`, pdfplumber (avoid PyMuPDF, which is AGPL), rapidfuzz, jiter, slowapi, and pytest.
- Frontend: React, TypeScript, Vite, Tailwind (logical utilities `ms-/me-/ps-/pe-/start-/end-` and `rtl:`/`ltr:` variants only), Zod, Recharts, KaTeX, and react-markdown.
- E2E: Playwright and `@axe-core/playwright`.

## Commands (planned Makefile targets, README §11)

- `make setup` runs `uv sync`, `npm ci` and the Playwright Chromium install.
- `make dev` starts uvicorn on :8000 and Vite on :5173, with `/api` proxied to the backend.
- `make serve-mock` builds the frontend and serves it from FastAPI with `MOCK_LLM=1`. This is the deterministic mode.
- `make test-backend` runs `uv run pytest -q`. For a single test, `cd backend && uv run pytest tests/test_grounding.py::test_name -q`.
- `make lint` runs ruff, mypy, eslint, typecheck and the `dangerouslySetInnerHTML` grep.
- `make e2e` runs Playwright against `make serve-mock`. For a single spec, `npx playwright test e2e/tests/rtl.spec.ts --project=chromium-ar`.
- `make e2e-update` regenerates the visual baselines. They are OS-specific.
- These targets make **live** calls: `make test-live`, `make record-fixtures`, `make bench` and `make check-models`.
- For quick UI checks: `npx playwright screenshot --viewport-size=1280,800 http://localhost:8000 shot.png`, then read the PNG. Prefer the Playwright CLI over Playwright MCP.

## Architecture (the big picture)

Request flow: `POST /api/ask` → provider streams JSON → `stream.py` parses it incrementally (jiter partial mode) → each completed component goes through **Pydantic validation → `grounding.py` → `policy.py`** → it is emitted as an SSE event. Event names follow AG-UI (`RUN_STARTED`, `TEXT_MESSAGE_*`, `COMPONENT_PLANNED`, `COMPONENT`, `COMPONENT_DROPPED`, `WARNING`, `METRICS`, `RUN_ERROR`, `RUN_FINISHED`; see `docs/protocol.md`). The client reads SSE with `fetch` + `ReadableStream`, not `EventSource`, because the endpoint is a POST. `/api/ask_text` produces the plain-prose "Before" panel.

- **The catalog is defined once** in `backend/app/catalog.py` (Pydantic, `additionalProperties: false`). `to_gemini_schema()` turns `const` into `enum`, inlines `$ref` and strips `title`/`default`/`examples`. `scripts/export_schema.py` writes `frontend/src/catalog/schema.json`, and the Zod schemas in `frontend/src/catalog/schemas.ts` must stay equivalent to it. Gemini does not enforce `minLength`/`maxLength`/`uniqueItems`, so Pydantic and Zod enforce them. `answer_text` comes first in the schema because property order drives streaming.
- **`SCHEMA_MODE=single|plan`.** In plan mode one call returns a plan, then each component gets its own call. Use it if Gemini rejects the full schema with a 400.
- **Grounding** checks claims against `visible_text` only. `visible_text` excludes characters under 4 pt, near-white characters and characters outside the crop box. `all_text` is used only to detect hidden text and emit `HIDDEN_TEXT_DETECTED`. Both the quote and the page go through `normalize()` (NFKC, Arabic digit and separator folding, removal of tashkeel and tatweel, alef/ya/ta-marbuta unification, hyphen joining, lowercasing). The quote check is `partial_ratio ≥ 90`, with a ±1 page fix. Numbers must appear in the quote, within ±0.05 or one decimal place of rounding. Quotes stay verbatim English even in Arabic answers.
- **Policy** (also stated in the system prompt) rules: `needs_visual=false` → no components; at most 3 components, prioritized `comparison > steps > chart > table > diagram > formula > text`; the quiz is always last and at most one is allowed; a chart with fewer than 3 verified points becomes a table, and a table with fewer than 2 rows becomes text; comparisons need matching attribute keys. Every drop emits `COMPONENT_DROPPED`.
- **Providers** implement the `LLMProvider` protocol in `backend/app/providers/`:
  - `gemini` uses the Files API (uploads are reused for up to 47 h), `generate_content_stream`, and `thinking_level` (never also `thinking_budget`). Temperature stays at 1.0.
  - `openai_compat` sends the visible text with `[[page N]]` markers. It is tested only with respx mocks.
  - `mock` replays `fixtures/answers/` in chunks. Select it with `LLM_PROVIDER`; `MOCK_LLM=1` forces mock. In mock mode only, the `X-Mock-Fixture: malformed/<name>` header forces a specific fixture.
- **Caching and metrics.** Keep the stable prefix (system prompt + catalog + file) first so Gemini's implicit cache can hit. The app cache lives in `data/cache.sqlite`, keyed on sha256(pdf) + normalized question + lang + model + `PROMPT_VERSION`. Costs come from `backend/app/prices.json`, which has `valid_from`/`valid_until` dates (3.8 Flash prices double on 2027-01-01). Thinking tokens are billed at the output rate.

## Non-negotiable rules

- **The live-call budget is 15 Gemini calls for the whole build.** Count every call in `BUILD_LOG.md`. Build against `MOCK_LLM=1` by default.
- Default `MODEL=gemini-3.8-flash` and `FALLBACK_MODEL=gemini-3.1-flash-lite`. Do not use `gemini-2.5-*` or `gemini-3.5-flash`. Verify model IDs and SDK field names with `make check-models` instead of trusting the README.
- XSS: never use `dangerouslySetInnerHTML` (an ESLint rule and a grep enforce this). Use react-markdown without `rehype-raw` and with an `allowedElements` whitelist. Never render model-supplied URLs, links or images. Draw diagrams with our own SVG; do not use Mermaid. Run KaTeX with `trust: false`.
- The key is read by the backend only, and a test greps `frontend/dist` for `AIza`. Strict CSP applies when FastAPI serves the build.
- RTL: each component root sets `dir`/`lang`, and model strings get `dir="auto"`. Mixed tokens go in `<bdi>`, and quotes and KaTeX go in LTR islands. In RTL, Recharts uses `XAxis reversed` and `YAxis orientation="right"`. Never apply `letter-spacing` to Arabic text. The font is self-hosted IBM Plex Sans Arabic. Display Western digits by default.
- Fixture quotes must be copied from the real `visible_text` of `cot.pdf` and must pass `grounding.py`.
- Stop rules (README §2): ask the user only when the key is missing after all mock-capable phases are done, when no usable model ID exists, when a billing or permission error can't be fixed by configuration, or when a dependency install fails after two attempts. Otherwise decide, log the decision and continue.
