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
| 10 | 2026-10-29 | `diag_gemini.py schema` again (~15 min later) | 3.8-flash | **400 INVALID_ARGUMENT** (flat schema, no PDF, no media_resolution) |
| 11 | 2026-10-29 | `diag_gemini.py base` (thinking=low, no schema, no PDF) | 3.8-flash | 503 UNAVAILABLE (high demand) |
| 12 | 2026-10-29 | q1 AR, real pipeline, `SCHEMA_MODE=json` | 3.8-flash | accepted (no 400), but **no chunk in 150 s** → client timeout |
| 13 | 2026-10-29 | `diag_gemini.py base` | 3.8-flash | 503 UNAVAILABLE (high demand) |
| 14 | 2026-10-29 | q1 AR via `record_live.py --provider gemini --retrieval on` | 3.8-flash | no response in 240 s → timeout |

**14 of 15 used; 1 left for the user** (e.g. `make test-live` = 1 call once the model is healthy).

**Conclusion.** Validation runs before the capacity check: the schema requests (1, 2, 4, 10) are rejected with 400, while the no-schema requests (11, 13) pass validation and hit 503. So `response_json_schema` with this catalog is rejected, and the thinking config is fine. `SCHEMA_MODE=json` (no API schema; schema text in the cached system prompt; strict Pydantic validation unchanged) is now the default. It passed validation in call 12 but couldn't be measured end to end because of the overload. **No live answer, latency or cost was measured.** Stop rule 3 (billing/permission) does not apply, so the build continued in mock mode.

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

## Phase 10 — hand-off

- Checked: light and dark mode follow `prefers-color-scheme` (colour tokens in `frontend/src/styles/index.css`), AR and EN, 1280 and 390 px.
- **D18 — Default `SCHEMA_MODE=json`** (see the live-call conclusion above). `flat`, `single` and `plan` remain available.

### Measured cost & latency

- **Live: not measured.** No live call succeeded (400 for API schemas, then 503 / hang from overload). The cost model is tested against prices.json for both price periods.
- **Mock** (MOCK_TTFT_MS=400, 40 chars / 30 ms): time to first text ≈ 0.4–1.0 s; total ≈ 3.2 s for q1 (3.7 KB of JSON) and 1.3–1.9 s for q2–q6; repeat question (app cache) 0.0 s in the UI and under 300 ms (asserted in `cache.spec`). Mock-reported tokens ≈ 24.1k input (43 pages × 560) plus output ≈ chars/3, so ≈ $0.02 per answer at 3.8 Flash prices (illustrative only).

### Known limitations

- **No live verification.** The Gemini path (Files API upload, JSON mode, streaming, usage metadata, fallback) is unit-tested with mocks and passed `count_tokens`, but never produced a full live answer. Run `make test-live` (1 call) when the model is healthy; 2 of the 15 budgeted calls remain.
- **Fixtures are hand-authored**, not recorded. The Egyptian Arabic was written by the build agent and has not been reviewed by a native speaker.
- **Scanned PDFs**: pages without a text layer give `unverified` badges; there is no OCR.
- **Arabic PDF extraction**: pdfplumber on RTL Arabic PDFs was not tested (the demo PDF is English). NFKC folds presentation forms, but visual-order extraction could still break quote matching.
- **Values only in figures** (e.g. Figure 4) can't be grounded; q2 uses Appendix Table 2 instead.
- **Diagram bidi**: an Arabic SVG label with inline arithmetic reorders visually (SVG has no `bdi`).
- **Mock latency target**: q1 misses the ≤ 2 s mock total (3.2 s) because of the spec'd 40-char / 30 ms chunking.
- **Visual baselines** are Windows-specific.
- **Phase 11 (AG-UI / CopilotKit / A2UI)** was not attempted (optional). `docs/protocol.md` describes the mapping.

### Final checks (2026-10-29)

- `make lint`: pass. `make test-backend`: **124 passed**. `make e2e`: **90 passed, twice in a row** (cache-timing now runs alone in its own project after the parallel ones; it once measured a cache hit at 301 ms while 4 workers were parsing PDFs, just over the 300 ms limit).

## Groq provider + retrieval (2026-10-29, after hand-off)

### Model check (Groq `GET /models`, no generation)

Chat models on the account: `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `openai/gpt-oss-safeguard-20b`, `qwen/qwen3.8-27b`, `allam-2-7b` (4K context). Per Groq's structured-outputs docs, strict `json_schema` works on gpt-oss-120b/20b and qwen3.8-27b, **but not together with streaming**. The free tier is listed at 8K TPM / 30 RPM / 1K RPD for all three. Prices (console.groq.com/docs/models): gpt-oss-120b $0.15 in / $0.60 out per 1M tokens; **qwen3.8-27b is a *preview* model** ("evaluation purposes only") at $0.80 / $4.00. It is kept as the rate-limit fallback only.

### Decisions

- **D19 — Groq is a thin subclass of the OpenAI-compatible provider** (`providers/groq.py`). Structured answers are one **non-streamed** call with strict `json_schema` (Groq can't stream structured outputs); the JSON then goes through the same parse → validate → ground → policy → SSE pipeline, so time to first token equals the total time. The "Before" prose answer does stream. `reasoning_effort=low` for gpt-oss (reasoning tokens count against TPM).
- **D20 — Strict schema** (`catalog.strict_schema`): every property is required, optional ones become nullable, every object has `additionalProperties: false`, and length/count keywords plus descriptions are removed (their limits move into one compact line of the system prompt). The union schema is ~6.3 KB ≈ 1.9K tokens (2.9K with descriptions). Strict-mode nulls are stripped before Pydantic validation.
- **D21 — Retrieval** (`app/retrieval.py`): ~600-character chunks, BM25 (no new dependency), query expansion (a small Egyptian-Arabic→English glossary for common question words, plus English synonyms such as size→scale), a numeric-density boost for quantitative questions, "Table N:" captions pulling in their table body, a mild early-page prior (×1.5 on page 1 → ×1.0 on the last page), and page 1's first chunk always included. Chunks are packed in page order with `[[page N]]` markers until the estimated budget is used. Grounding still checks quotes against the full page text.
  - **Recall** against the pages the hand-authored fixtures cite, at the real ~2.2K-token context budget: **23/28**. Every question's key page is retrieved (q2 → Table 2 on page 21 with the PaLM rows, in both languages). Misses: q3-EN pages 7–8 (commonsense/symbolic sections), q5 page 21 (both languages), q5-AR page 3.
  - Embeddings were considered (cross-lingual quality) but not added: a local multilingual model would mean a ~220 MB download and onnxruntime, and a hosted embedding API would send the document to another service, which is the opposite of the sovereignty story.
  - `RETRIEVAL=auto` turns it on for Groq/openai_compat; `RETRIEVAL=on` also applies it to Gemini (text instead of a Files API upload).
- **D22 — Token budget.** `RETRIEVAL_MAX_PROMPT_TOKENS=5800` is an *estimate* (chars/3.6 for prose, /3.2 for schema JSON). Live Groq prompts measured **~13% below** the estimate (the first call: 4,796 real vs 5,500 estimated), so real prompts stay under 6,000. Groq's 429 body showed "Requested 5482" for a 5,066-token prompt, so `max_tokens` (2,400) is **not** reserved in full against TPM.
- **D23 — 429 handling.** `retry-after` (seconds) or `x-ratelimit-reset-tokens` (`2m59.56s`) is parsed into `ProviderError.retry_after`. The retry loop waits exactly that long when it fits (`RATE_LIMIT_MAX_WAIT_S=30` and the request deadline, with a `WARNING RATE_LIMIT_WAIT`). Otherwise it jumps straight to the fallback model, which has its own per-model token bucket. If both are limited, the result is `RUN_ERROR RATE_LIMITED`. Verified live: a 24.5 s retry-after was waited out and the retry succeeded.
- **D24 — Provider switch.** `PROVIDER=gemini|groq` (`LLM_PROVIDER` still accepted). `/api/ask` takes an optional `provider`; `/api/config` lists providers with their model and availability (key present). The header has a Gemini|Groq switch, remembered in localStorage and disabled for providers without a key. Metrics show the provider · model badge and the retrieved pages. In mock mode the mock answers *as* the chosen provider and replays `fixtures/answers/live/<provider>/` when a live recording exists, so the live Groq answers can be demoed offline. The answer cache key includes provider + model.
- **D25 — Positive visual guidance in the prompt (`PROMPT_VERSION=v2`).** The first live Groq answer to q1 was correct but `needs_visual=false`: with low reasoning effort, gpt-oss followed the text-only restraint example too literally. The prompt now maps question shapes to components (compare → comparison, how much → chart, which … → table, show how → diagram, review → flashcards).
- **D26 — Over-long strings are truncated, not dropped.** Neither Gemini nor Groq enforces `maxLength`. A live Groq comparison was dropped as `invalid` because one value was 86 characters against a limit of 80. Now `string_too_long` / `too_long` errors are repaired (cut to the limit with "…", lists trimmed) and the component is validated again; any other error still drops it. The event reports `truncated_fields`. Quotes stay verbatim prefixes, so grounding is unaffected.

### Live results per provider (2026-10-29)

**Groq — `openai/gpt-oss-120b` (fallback `qwen/qwen3.8-27b`), retrieval on, strict schema, `PROMPT_VERSION=v2`.** 12 live answers saved in `fixtures/answers/live/groq/` (the raw model JSON) + `report.json`. "total s" is wall time **including rate-limit waits**; the model's own time is `upstream_ms`.

| Q | lang | model | total s | prompt tok (est budget) | out+think tok | cost $ | pages sent | components | verified | citations dropped | dropped |
|---|---|---|---|---|---|---|---|---|---|---|---|
| q1 | ar | openai/gpt-oss-120b | 2.4 | 4880 (5800) | 704 | 0.0012 | 1,2,3,4,5,6,7,8,9,28 | comparison | 0/1 | 1 | — |
| q1 | en | openai/gpt-oss-120b | 26.8 | 5066 (5800) | 750 | 0.0012 | 1,2,4,5,6,7,8,11,18,23 | comparison | 0/1 | 3 | — |
| q2 | ar | openai/gpt-oss-120b | 50.6 | 5846 (5800) | 665 | 0.0013 | 1,2,4,5,6,7,16,21,22 | text only | 0/0 | 0 | chart:invalid |
| q2 | en | openai/gpt-oss-120b | 44.7 | 5511 (5800) | 1100 | 0.0015 | 1,2,4,5,6,7,11,16,21,23,37 | chart | 1/1 | 0 | — |
| q3 | ar | qwen/qwen3.8-27b (fallback) | 44.6 | 3430 (5800) | 453 | 0.0046 | 1,2,3,4,7,8,9,13,16,18,20,26 | table | 1/1 | 0 | — |
| q3 | en | openai/gpt-oss-120b | 1.6 | 4840 (5800) | 473 | 0.0010 | 1,2,3,4,5,6,7,9,13,18,19,26 | text only | 0/0 | 0 | table:insufficient_verified_rows |
| q4 | ar | openai/gpt-oss-120b | 38.7 | 4901 (5800) | 139 | 0.0008 | 1,2,5,6,9,10,11,15,18,27,30,42 | text only | 0/0 | 0 | — |
| q4 | en | openai/gpt-oss-120b | 17.5 | 4930 (5800) | 151 | 0.0008 | 1,2,5,6,9,12,14,15,18,28,30,31,38 | text only | 0/0 | 0 | — |
| q5 | ar | openai/gpt-oss-120b | 38.0 | 4906 (5800) | 793 | 0.0012 | 1,2,3,4,5,6,7,17 | flashcards | 1/1 | 0 | — |
| q5 | en | openai/gpt-oss-120b | 45.2 | 4993 (5800) | 654 | 0.0011 | 1,2,3,6,14,15,16,34,41 | flashcards | 1/1 | 0 | — |
| q6 | ar | openai/gpt-oss-120b | 40.0 | 4791 (5800) | 210 | 0.0008 | 1,2,3,4,5,6,7,8,9,11,25 | text only | 0/0 | 0 | — |
| q6 | en | openai/gpt-oss-120b | 1.5 | 4720 (5800) | 380 | 0.0009 | 1,3,4,6,7,8,18,28,39 | diagram | 1/1 | 0 | — |

| Groq summary | value |
|---|---|
| Model time per answer (`upstream_ms`) | **p50 1.8 s, max 4.3 s** (non-streamed, so time to first token = total) |
| Wall time per answer | p50 38.7 s, max 50.6 s: **dominated by 429 waits** (8K TPM vs ~5.3–6.7K tokens requested per answer ⇒ ~1 answer per 45 s); 10 of 12 runs waited at least once, 1 switched to the qwen fallback |
| Prompt tokens (real, from usage) | mean 4,901, **max 5,846** (q2-AR: numeric table, estimate was low; the estimator now counts digits at ~2 chars/token) |
| Cost | mean **$0.0014** per answer (gpt-oss-120b); the qwen fallback answer cost $0.0046 |
| Components | 9 produced → **5 verified, 2 partial (shown), 2 dropped**; 3 answers text-only by the model's choice (q4 ×2 correctly; q6-AR should have been a diagram) |
| Grounding pass rate | **components: 5/7 shown fully verified (71%), 5/9 produced (56%)**; **citations: 24/34 quotes verified (71%)** |
| Dropped by grounding/validation | q2-AR chart: every quote was a 7-character cell fragment ("20B 4.4", min 10) and the series mixed model families: correctly rejected. q3-EN table: 2 of 3 row quotes paraphrased (fuzzy 68/57): correctly rejected (needs ≥ 2 verified rows) |
| Errors | 1 in the first pass (q6-EN: Groq's own validator rejected the model's JSON, `json_validate_failed`). Now retried as `OUTPUT_INVALID`; a rerun of q6-EN gave a verified diagram in 1.5 s |

**Gemini — `gemini-3.8-flash`.** Not measurable: the one extra live call (q1-AR, `RETRIEVAL=on`, call 14 of 15) got **no response in 240 s** (timeout), continuing the 503 / hang pattern from earlier. 1 Gemini call remains. Mock-mode Gemini figures are in the Phase 10 section.

**Takeaways for the interview.** (1) Groq answers in ~2 s of model time, which is fast enough for the live demo, but the free tier's 8K TPM allows about one full answer per 45 s; ask Groq questions about a minute apart, or the second one will wait (up to 30 s) or switch to the qwen fallback. (2) Grounding visibly earns its keep on live output: 10 of 34 live quotes failed verification and were removed or downgraded, never shown as verified. (3) Retrieval kept every live prompt under 6,000 real tokens, and the key page was sent in all 12 runs (e.g. page 21 for q2).


## Design pass (2026-10-29)

Options were shown as mockups (`data/design-options.html`); the user picked **1B 2C 3B 4B 5A 6C 7C 8B 9B** and asked to use React Bits. Frontend only: catalog, backend and logic are unchanged.

- **Palette (1B):** teal accent `#0F766E`, coral highlight `#C2462F` reserved for key numbers, soft teal-tinted surfaces, shadows instead of borders; full dark-mode token set. `@theme static` because Tailwind v4 drops theme variables it doesn't see used, and the band colours are referenced through a computed name.
- **Bands (2C):** each component type has a deep band colour with an icon and label (white text ≥ 4.5:1 in both themes). One card level only; steps are plain rows, quiz options are tiles, comparison columns are tints.
- **Lead (3B + 4B):** the first component's title is the large takeaway; when the answer has a chart, the largest verified gap (e.g. **+39.0 points at 540B**, 17.9% → 56.9% · p.21) sits beside it, and stat tiles show the gap at every category. All are computed in the UI from the chart's verified points (`lib/keyNumbers.ts`), never by the model. The answer text drops to 16px and follows the first visual.
- **Chart (5A):** 4px/3px lines, 5.5px points, soft gridlines, the peak marked by a coral dot (`zIndex` 1300, since Recharts 3 drew the line's point over it) and a label placed inward at the plot edge; RTL mirroring unchanged.
- **Before/After (6C):** inside the 760px column the text wall is the narrower side (13px, grey, masked fade, "…", word count) and the visual side is ~60%, with a "vs" badge (horizontal on phones).
- **Question area (7C):** single-line pill input with send button; the six demo questions as numbered full-text suggestions; the mock notice is a "Mock" badge in the header.
- **Width (8B):** one 760px column for header, Ask and Before/After; `grid-cols-[minmax(0,1fr)]` stops long content from widening the page on phones.
- **Quiz (9B):** 2×2 tiles (min-height 64px) with a real radio covering each tile (keyboard, screen readers, tests), Arabic letters أ ب ج د in Arabic; correct = green + ✓, wrong = rose + ✕, the rest dimmed.
- **React Bits:** `CountUp` (key number and tiles; needs `motion`, lazy-loaded so it's a 69 KB chunk off the main bundle) and `ClickSpark` (star burst from the correct tile, triggered through its ref) in `src/components/bits/`, MIT + Commons Clause, source read before use. ClickSpark was patched to add `sparkOnClick` and to update prop refs in a layout effect (our lint forbids ref writes during render). FadeContent was not used: it needs GSAP + ScrollTrigger (~70 KB) and hides content until a scroll trigger fires. Both components honour `prefers-reduced-motion`.
- **Tests:** Playwright runs with `reducedMotion: 'reduce'` (deterministic screenshots, and it exercises the reduced-motion path); the demo project records with full motion. Fixed during the pass: "Mock" badge contrast (4.3:1 → white on coral), a 30px horizontal overflow on phones, the peak label clipping/overlapping in RTL. 20 visual baselines regenerated after review; axe 0 violations; `make e2e` 94 passed twice; backend 167 passed.
- Review page: `data/design/index.html` (14 before/after pairs + dark mode; not committed, `data/` is git-ignored). Demo re-recorded: `demo/arif-visual-answers.gif` (2.3 MB).

## Any PDF, any question (2026-10-29)

- **`make serve` is the product** (live model from `PROVIDER` in `.env`, `MOCK_LLM=0` forced); `make serve-mock` stays for tests and offline demos. `.env` now has `PROVIDER=groq` (Gemini was unavailable all day; the header switch still offers it). Mock-mode tests pin `PROVIDER=gemini` (pytest settings and the e2e launcher), so a developer's `.env` can't change what fixtures they replay.
- **D27 — Query translation, not a glossary.** The CoT-specific Arabic glossary and paper-specific synonyms (authors→"google research", different→"standard") are gone; generic English synonyms stay. When the question's script differs from the document's (Arabic vs Latin), one call to `SMALL_MODEL` translates it for BM25 only; the answer model still gets the original question. Cached in SQLite (`kv` table). Best-effort: no Groq key, an error or a 429 → search with the original question. **`llama-3.1-8b-instant` is not available on this Groq account** (checked `GET /models`: only `openai/gpt-oss-20b`, `gpt-oss-120b`, `qwen3.8-27b`, `allam-2-7b`, guard/speech models), so `SMALL_MODEL` defaults to `openai/gpt-oss-20b` (Groq's cheapest, $0.075/$0.30 per 1M, strict JSON, own per-minute bucket). Document language = dominant script of its text (`ar`/`en`/`other`).
- **D28 — Table caption + body packed as one unit.** Under the real ~2.3K-token context budget, Table 2's caption fitted but its 263-token body did not, and smaller chunks filled the gap. Captions and bodies are now packed together (or the body alone).
- **D29 — OCR for scanned PDFs.** `Smart Job Matching topic.pdf` is a 15-page slide deck exported as images (0 characters of text). RapidOCR (pip, onnxruntime, models bundled, fully local) recognises pages without a text layer at ~3 s/page; it runs in the background after upload (`status: "reading"`, the UI polls), questions about that document wait for it, and the text becomes the page's visible text (flagged `ocr`, `OCR_USED` warning), so retrieval and grounding work on scans. Arabic scans are not covered by RapidOCR's default models.
- **D30 — Documents belong to a browser.** The document list was server-global (every visitor saw every upload; parallel e2e tests fought over it). Each browser now sends a random `X-Client-Id`; uploads are tagged with it, `GET /api/documents` lists only the owner's, and delete requires ownership. Document ids stay unguessable UUIDs for page/ask access.
- **Multiple PDFs:** a sidebar lists the browser's documents (restored after reload; the server keeps them 48 h), adds several at once, switches (each document keeps its last answer in memory and its question history in localStorage), and deletes with a two-step confirm.
- **Suggestions:** the six CoT demo questions show only when the loaded PDF is `cot.pdf` (by SHA-256). Other documents get 4 questions generated by `SMALL_MODEL` from their first ~6,000 characters, in the UI language, cached per document + language; generic questions are the fallback.
- **Tests:** backend 170 passed; new: ownership, OCR on a generated image-only PDF, suggestions cached/fallback (respx), translation used for retrieval only and cached, no translation when languages match, caption/body packing. e2e: `docs.spec` (two PDFs, demo vs generated suggestions, answers restored on switch, history, delete, reload, another browser sees nothing) and a second `@live` test (non-CoT PDF, typed question, verified visual).

### Live check: 3 real PDFs × 3 free-form questions (Groq gpt-oss-120b, `make serve`, HTTP, 50 s apart)

Run with `PROMPT_VERSION=v2` and the 5,800 estimated budget; the fixes after it are listed below. PDFs: `resume-ner-peft.pdf` (3 pages, text), `smart-job-matching.pdf` (15 slides, **image-only → OCR 19.6 s**), `cot.pdf` (43 pages). Suggestions were generated for all three in both languages.

| PDF | Question | lang | visual | verification | latency (model) | prompt tok | translated | failure |
|---|---|---|---|---|---|---|---|---|
| resume-ner-peft | How does LoRA compare with full fine-tuning in this report | en | comparison | partial | 2.0 s (2.0 s) | 3744 | no | — |
| resume-ner-peft | إيه الخطوات اللي عملوها علشان يدربوا الموديل؟ | ar | steps | verified | 2.4 s (1.8 s) | 3748 | yes | — |
| resume-ner-peft | Quiz me on the key ideas of this report. | en | quiz | verified | 2.4 s (2.4 s) | 3740 | no | — |
| smart-job-matching | Compare content-based, collaborative and hybrid recommenda | en | comparison | partial | 24.6 s (2.7 s) | 4774 | no | — |
| smart-job-matching | إزاي LinkedIn و Indeed بيرشحوا الوظايف للناس؟ | ar | comparison | partial | 3.7 s (2.1 s) | 4781 | yes | — |
| smart-job-matching | Which steps does a job recommendation pipeline go through? | en | steps | verified | 1.7 s (1.7 s) | 4774 | no | — |
| cot | إيه حدود الـ chain-of-thought اللي الورقة بتعترف بيها؟ | ar | text only | — | 1.7 s (1.1 s) | 4694 | yes | — |
| cot | Which tasks did chain-of-thought help least, and why? | en | text only | — | 0.9 s (0.9 s) | 4639 | no | — |
| cot | Make a table of the commonsense benchmarks and what each o | en | text only | — | 1.5 s (1.5 s) | 4781 | no | table:insufficient_verified_rows |

**Summary:** 9/9 answered, 0 errors. A visual appeared for **6/9** questions (6 components: **3 fully verified**, 3 partial = shown with unverifiable citations removed). Model time 0.9–2.7 s; one 24.6 s answer was waiting out Groq's per-minute token limit. Every Arabic question was translated for search. Real prompts 3,740–4,781 tokens. Text-only answers: two CoT questions where the model judged no visual useful, and the CoT benchmark table, which grounding dropped: the model's StrategyQA quote was elided and editorialised ("... (context implies multi-step reasoning)"), so it could not verify, and one verified row is below the table minimum.

**Fixes from the live checks (after this run):**
- **D31 — quotes are one contiguous span** (prompt v3): no "...", no added words.
- **D32 — Groq rejecting its own output** (`json_validate_failed`, gpt-oss and qwen) used to cost the whole answer; the retry now uses plain JSON mode and our validation drops only the bad component. Detection keys on the error code.
- **D33 — comparisons with one attribute per item** were the recurring `invalid` drop (now logged with the failing rule). Groq strict mode accepts `minItems` but checks it after generating, so the fix is the prompt (v4: every item has at least 2 attributes). The Arabic smoke test then passed first try.
- **D34 — budget re-calibrated:** `RETRIEVAL_MAX_PROMPT_TOKENS` = 6,200 estimated, measured live at **5,104 real tokens** (< 6,000) with page 21 still retrieved.
- `make test-live` now sets `LIVE=1` (it silently skipped before) and runs one worker at a time; the second live test waits 65 s for Groq's per-minute budget.
- **Live tests:** both `@live` tests passed against the real model (Arabic CoT smoke test; resume-NER typed question with a grounded visual and page chips).

