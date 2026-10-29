# BUILD_LOG

## Live-call counter

Budget: 15 Gemini **generation** calls. `models.list`, `files.upload` and `count_tokens` are logged separately; they don't use generation quota.

Counted as **requests that reached the API** (a call that retried counts once per attempt).

| # | Date | Purpose | Model | Result |
|---|---|---|---|---|
| 1 | 2026-10-29 | Phase 2 schema check, q1 EN (anyOf schema with min/maxLength) | 3.8-flash | 400 INVALID_ARGUMENT |
| 2 | 2026-10-29 | same, with error reporting | 3.8-flash | 400 INVALID_ARGUMENT |
| 3 | 2026-10-29 | anyOf schema, length keywords moved to descriptions, bool enum removed | 3.8-flash | client timeout at 45 s, no text (probably 503s + retries, statuses weren't logged yet) |
| 4 | 2026-10-29 | same schema, 150 s timeout | 3.8-flash | 400 INVALID_ARGUMENT after 13 s |
| 5–8 | 2026-10-29 | flat schema (no anyOf), q1 EN | 3.8-flash ×3, 3.1-flash-lite ×1 | 3× retryable error on primary → fallback → 400 on flash-lite. Retries burned 4 requests: recording now never retries |
| 9 | 2026-10-29 | `diag_gemini.py schema` (tiny prompt + flat schema, no PDF) | 3.8-flash | **503 UNAVAILABLE "model is currently experiencing high demand"** |

Non-generation calls: 1× models.list, 1× files.upload, 1× count_tokens (Phase 0 `make check-models`).

## Phase 0 — environment

- OS: Windows 11 Pro. Shell for `make`: Git Bash (`sh`). Installed `uv` via `pip install --user uv` and GNU make via `winget install ezwinports.make`.
- Python 3.12.16 (uv-managed), uv 0.13.6, Node v24.15.0, npm 11.12.1, Playwright 1.64.1 (Chromium), ffmpeg 8.0.1, git 2.49.0.
- Backend versions (uv.lock is authoritative): fastapi 0.162, google-genai 2.33, pydantic 2.14, pdfplumber 0.11.10, rapidfuzz 3.14, jiter 0.18, slowapi 0.1.10, pytest 9.2, ruff 0.17, mypy 2.4, reportlab 5.1, respx 0.23.
- Frontend versions (package-lock.json is authoritative, deps pinned with `-E`): React 19.3, Vite 8.3, TypeScript 7.0, Tailwind 4.3 (via `@tailwindcss/vite`), Zod 4.6, Recharts 3.10, KaTeX 0.19, react-markdown 10.1.
- `cot.pdf`: downloaded from arxiv.org/pdf/2201.11903 (curl needed `--ssl-no-revoke`: Windows schannel revocation server offline). **SHA-256 `7d9f878c23b460e4566aa4ec9201b1abfb3b8faefb2b1356e411cb90fef72a12`, 43 pages, 891,773 bytes.**

### Model check (2026-10-29)

- `gemini-3.8-flash`: FOUND. `gemini-3.1-flash-lite`: FOUND.
- `count_tokens(gemini-3.8-flash, cot.pdf via Files API)` = **24,081 tokens = 560 tokens/page** (the README estimate of ~258/page was low; the count includes the extracted text layer).
- SDK field names verified against google-genai 2.33: `ThinkingConfig.thinking_level` (enum MINIMAL/LOW/MEDIUM/HIGH), `GenerateContentConfig.response_json_schema`, `.media_resolution` (MEDIA_RESOLUTION_MEDIUM), `usage_metadata.{prompt_token_count, cached_content_token_count, candidates_token_count, thoughts_token_count, total_token_count}`. All match the README.
- `jiter.from_json(buf, partial_mode="trailing-strings")` exists and works.
- Prices re-checked at ai.google.dev/gemini-api/docs/pricing: unchanged from README section 1. New details: 3.8 Flash cache **storage** also doubles on 2027-01-01 ($0.50 → $1.00 /1M/h); 3.1 Flash-Lite has no free-tier caching; PDF (`DOCUMENT` modality) tokens are billed at the image rate.

## Decisions

- **D1 — Linter.** The Vite 8 template ships **oxlint** instead of ESLint. Kept oxlint (faster, zero config) and enabled `react/no-danger` as an error; `make lint` also greps `frontend/src` for `dangerouslySetInnerHTML`.
- **D2 — Text extraction.** pdfplumber `extract_text(x_tolerance=1.5)`: the default tolerance (3) glued words together in the LaTeX-typeset CoT paper ("Weexplorehow…"), which would break quote matching.
- **D3 — Hidden-text threshold.** The real paper has dark figure tick labels under 4 pt (e.g. 27 on page 5). Hidden chars are classified as `white`, `offpage` or `tiny`; a page is flagged when white+offpage ≥ 10 or tiny ≥ 60. All hidden chars are still excluded from `visible_text`. cot.pdf: 0 flagged pages; injection.pdf: page 1 flagged.
- **D4 — Doc store.** Parsed docs are kept in memory with a JSON sidecar in `data/docs/` so a server restart keeps them; cleanup removes both after 48 h.
- **D5 — Schema modes.** Gemini returned `400 INVALID_ARGUMENT` for the full catalog schema (9-branch `anyOf`, ~9 KB) even after removing `minLength`/`maxLength` (now description hints; Pydantic enforces them) and the boolean `enum` (`steps.ordered`; the server sets it to `true`). Added `SCHEMA_MODE=flat`: one component object with a `type` enum and every type's fields optional, no `anyOf`, no `additionalProperties` (6.3 KB). The server projects each component onto its real model and validates strictly, so the contract is unchanged. `plan` is implemented too but costs 1 + up to 3 calls per answer. Live status: see the call log and Phase 2 notes below.
- **D6 — Fixtures are hand-authored.** The live budget went on schema debugging and a 503 overload ("high demand") on gemini-3.8-flash, so all q1–q6 AR/EN fixtures were written by hand with quotes copied from `visible_text` of the real `cot.pdf` (marked `"source": "hand-authored"` in `fixtures/answers/cot/meta.json`). `scripts/check_fixtures.py` and `tests/test_fixtures.py` prove each one is fully `verified`.
- **D7 — q2 numbers.** GSM8K-by-model-size values are in the text layer: Appendix Table 2 (page 21), e.g. PaLM 8B 4.9→4.1, 62B 9.6→29.9, 540B 17.9→56.9. Figure 4's values are image-only and are not used.
- **D8 — Grounding hardening beyond the README.** (a) Numbers must appear in the quote *and* that quote number must appear on the page, so a fuzzy-matching quote (score ≥ 90) with one digit changed can't verify an invented value. (b) If `partial_ratio` < 90, retry with all spaces removed (PDF extraction sometimes drops spaces). (c) Digits glued to words (`GSM8K`, `GPT-3`, `code-davinci-002`) are identifiers, not numbers.
- **D9 — Streaming cap.** The first two non-quiz components are emitted as soon as they are validated (lower latency). Later ones are held until the stream ends, then the remaining slot(s) go to the highest-priority held component; a quiz is held and always emitted last.
- **D10 — Retries.** 429/503 → 2 retries with backoff + jitter → 1 attempt on `FALLBACK_MODEL` (`WARNING FALLBACK_MODEL_USED`). Only before any output has streamed. Recording scripts never retry, so one recording = one request.
- **D11 — Parse cache.** Parsed page layers are memoised by SHA-256 in-process (re-uploading `cot.pdf` is instant; the test suite went from 177 s to 14 s). Limits are re-checked on a cache hit.
- **Tool note.** The tool transport decodes `\uXXXX` escapes in commands/content; source files that need escapes build them with `chr(92)` or use the literal characters.

## Phase 4 — frontend

- Checked with Playwright (`e2e/helpers/shoot.mjs`, `crop.mjs`) in AR and EN at 1280 and 390: RTL/LTR mirroring correct, Arabic letters join, no horizontal scroll at 390 px, the q2 chart shows a page chip for every point, the second identical question hits the app cache (0.0 s, "cached").
- **D12 — e2e package.** `e2e/` is its own npm package (`@playwright/test`, `@axe-core/playwright`) so specs and helpers resolve their imports; `make setup` installs it.
- **D13 — Bundle.** Recharts and KaTeX are lazy-loaded (main JS 1.1 MB → 473 kB; chart 390 kB and formula 260 kB load on demand).
- **D14 — Diagram layout.** A "snake" flow layout (rows alternate direction, mirrored in RTL), with 1, 2 or 3 nodes per row chosen from the measured width, so labels stay readable on phones. Edge labels are drawn above the nodes.
- **D15 — Mock replay is compact JSON.** Fixtures are pretty-printed; the mock replays them minified, like a real model. At the spec's 40 chars / 30 ms, q1 (3.7 KB) still takes about 3.2 s in mock mode, above the ≤ 2 s mock target; q2–q6 take ≤ 1.9 s.
- Known: in the Before/After view, a cached visual answer shows $0 / 0.0 s, so the cost/latency comparison is only meaningful on a first (uncached) run.

## Phase 5 — security

- `curl -I /` shows the CSP, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` and `X-Frame-Options: DENY`. The `AIza` grep of `frontend/dist` is empty. `make lint` also runs the `dangerouslySetInnerHTML` grep and the Zod↔Pydantic schema check.
- Defence in depth for model strings: the server strips URLs from component props (`[link removed]`); the client also defangs URLs in every model string, renders the answer text as plain text, and escapes `<` before react-markdown, so raw HTML shows as literal characters. KaTeX renders through `katex.render` into a ref (`trust:false`, `maxSize:10`, `maxExpand:100`).
- The `X-Mock-Fixture` header is honoured only by the mock provider, and only names matching `^[a-z0-9_]+/[a-z0-9_]+$`.

## Phase 6 — RTL / bilingual

- Screenshots in AR and EN at 1280 and 390 px: `html[dir][lang]` switch, mirrored header and tables, chart `XAxis reversed` + `YAxis` on the right in RTL, a snake diagram mirrored in RTL, quotes in LTR islands, no horizontal scroll at 390 px, Arabic joining intact (no letter-spacing on Arabic).
- Known quirk: an Arabic diagram label with inline arithmetic ("23-20=3، 3+6=9") goes through bidi reordering inside SVG `<text>`; SVG has no `<bdi>`. It is readable but not ideal.

## Phase 7 — metrics & cache

- `METRICS` event on every run; the strip shows time · tokens · cost · verified count, and the drawer shows each component's `reason` plus the raw JSON. A repeat question replays from SQLite (`app_cache_hit: true`, 0.0 s in the UI). Cost maths for both price periods is covered in `tests/test_providers.py`.

## Phase 8 — Playwright

- `make e2e`: **91 passed, twice in a row** (2.0 and 2.2 min) across `chromium-ar`, `chromium-en` and `mobile-ar` (390×844). The `@live` test is excluded from `make e2e`.
- axe (`wcag2a`, `wcag2aa`) reports **0 violations** after q1, q2, q3, q5 and q6 render, in both locales.
- 20 visual baselines (9 component types + Before/After, AR and EN) in `e2e/tests/__screenshots__/`. They are specific to the OS (Windows/Chromium 1.64) and mask the timing value.
- Bugs found by the suite and fixed: (1) the chart's screen-reader table caused 39 px of horizontal scroll at 390 px in RTL (`sr-only` on a `<table>` doesn't shrink it; it is now on a wrapper div); (2) four parallel uploads of the same PDF took 44 s (GIL thrash), fixed with a per-hash parse lock (7 s); (3) Recharts 3 dropped the `.recharts-xAxis` class, so the tick test now selects by label; (4) the formula fixture's `\times` had been turned into a tab by the tool transport.
- **D16 — Test-only headers.** In mock mode only: `X-Mock-Fixture: <dir>/<name>` forces a fixture, and `X-No-Cache: 1` bypasses the answer cache so streaming tests always see skeletons. The cache test uses a unique question so its first ask is always a miss.
- **D17 — e2e server.** `e2e/helpers/serve.mjs` (Playwright's `webServer`) finds `uv`, builds the frontend, wipes `data/e2e` and starts uvicorn with mock mode and high rate limits (the rate limiter itself is covered in pytest; the 429 UI is tested with `page.route`).

## Phase 9 — demo

- `make demo` → `demo/arif-visual-answers.webm` (4.3 MB), `demo/arif-visual-answers.gif` (2.1 MB, 960 px, 12 fps) and 8 key frames in `demo/shots/` (AR Before/After streaming, quiz, source panel, text-only q4, EN chart, metrics drawer, injection warning). Mock mode with `MOCK_TTFT_MS=900`.
- Not done: the optional live recording and `make bench` (10 live calls). The live budget was used up by schema debugging and the 503 overload.
