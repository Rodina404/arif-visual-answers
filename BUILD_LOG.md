# BUILD_LOG

## Live-call counter

Budget: 15 Gemini **generation** calls. `models.list`, `files.upload` and `count_tokens` are logged separately; they don't use generation quota.

| # | Date | Purpose | Model | Result |
|---|---|---|---|---|

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
