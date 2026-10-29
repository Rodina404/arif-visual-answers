<p align="center">
  <img src="docs/images/arif-logo.png" alt="Arif logo" width="112" height="112">
</p>

<h1 align="center">Arif Visual Answers</h1>

<p align="center">
  <b>Grounded visual answers and permission-gated actions over any PDF, Arabic first.</b><br>
  A prototype of what Arif (عارف) could add to Qriib: short answers with verified visuals,<br>
  and an assistant that understands the document, connects it to tasks and messages, and acts only with permission.
</p>

<p align="center">
  <img alt="Python 3.12" src="https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-SSE-009688?logo=fastapi&logoColor=white">
  <img alt="React 19" src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black">
  <img alt="Groq" src="https://img.shields.io/badge/Groq-gpt--oss--120b-F55036">
  <img alt="Gemini" src="https://img.shields.io/badge/Gemini-3.8%20Flash-4285F4?logo=google&logoColor=white">
  <img alt="Tests" src="https://img.shields.io/badge/tests-195%20backend%20%C2%B7%20113%20e2e-2EA44F">
  <img alt="RTL" src="https://img.shields.io/badge/Arabic-RTL%20first-6D28D9">
</p>

<p align="center">
  <a href="#the-problem">Problem</a> ·
  <a href="#what-it-does">Features</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#results">Results</a> ·
  <a href="#cost-plan">Cost plan</a> ·
  <a href="#quick-start">Quick start</a>
</p>

<p align="center">
  <img src="demo/arif-visual-answers.gif" alt="Demo: an Arabic question answered with a grounded comparison, then a quiz" width="820">
</p>

---

## The problem

Students and teams ask questions about long documents (papers, course notes, reports, meeting transcripts), mostly in Egyptian Arabic mixed with English terms. Three things go wrong with a plain chat answer:

1. **It is a wall of text.** The user needs the number, the trend, the steps or the owners, not 300 words.
2. **It can't be trusted.** A chart with one invented number is worse than no chart, and nothing tells the reader which page a claim came from.
3. **An assistant that acts can be steered.** Once the assistant can create tasks or write messages, text inside the document (even text the reader can't see) can try to make it act.

### Formulation

```text
Input
  D = (p1 … pn)        a PDF; each page has visible text V(pi) and hidden text H(pi)
                        (white, tiny or off-page characters; H is never evidence)
  q                     a question, 1–500 characters
  ℓ ∈ {ar, en}          the answer language (Egyptian Arabic, RTL, by default)

Output                  R(D, q, ℓ) = (t, C, A), streamed
  t                     a short answer in ℓ (≤ 700 characters)
  C = {c1 … ck}, k ≤ 3  typed components from a fixed catalog K (12 types)
  A                     proposed actions (tasks, message drafts), each in state "proposed"

Constraints
  G1 grounding     every claim in C cites (page j, quote s) with
                   fuzzy_match(s, V(p_j')) ≥ 90 for some j' ∈ {j−1, j, j+1}
  G2 numbers       every number in a claim appears in s AND in V(p_j')
  G3 agent items   a task's owner and due date appear in its cited sentence
  S1 permission    an action changes state only via an explicit user approval:
                   proposed → approved | rejected; nothing is ever sent
  S2 injection     text in D (visible or hidden) may cause a proposal, never an approval;
                   a proposal traced to H is flagged
  P1 latency       answer text starts streaming within seconds; repeat questions < 300 ms
  P2 cost          ≈ $0.001–0.002 per answer; fits Groq's free tier for a demo (8K tokens/min)

Policy             a claim that fails G1–G3 is removed, downgraded (chart → table) or dropped:
                   it is never shown as verified.
```

The design follows from these constraints: the model never writes free-form UI, only typed components that the server validates and checks against the page; and the agent's tools can only *propose*.

## What it does

| | |
|---|---|
| **Any PDF** | Upload one or several PDFs and switch or delete them from the "working in" bar; each keeps its question history. Scanned PDFs are OCR'd locally in the background. Arabic PDFs whose producer stores lines right-to-left with shaped glyphs (Chromium, Word) are restored to reading order. |
| **Any question** | Typed in Arabic or English. Suggested questions are generated for each document. |
| **Short answer + ≤ 3 visuals** | 9 visual types: `text`, `chart`, `comparison`, `steps`, `table`, `diagram`, `formula`, `quiz`, `flashcards`. The model chooses; a policy layer enforces the limits. |
| **Grounding** | Every data point carries a page number and a verbatim quote, checked against the visible text of that page (G1, G2). Anything that fails is removed or downgraded, never shown as fact. |
| **Agent mode** | Questions about decisions, owners, tasks or messages go to an agent loop with Groq tool calling (at most 4 steps, a timeout per step) and four tools: `search_document`, `extract_items` (decisions or action items, each citing its sentence ids), `create_task` and `draft_message`. Any other question keeps the visual-answer path. |
| **Permission gate** | `create_task` and `draft_message` only write proposals. Each appears in an action card with **Approve / Edit / Reject**; a task is saved only when the user who asked clicks Approve, and a draft is saved but never sent (S1). |
| **Agent cards** | 3 more catalog types built by the server from tool results, with the same validation and grounding: `decision_cards`, `task_cards` (G3) and `action_card`. |
| **Injection-safe actions** | Text in the document can lead to a proposal, never to an action (S2). A proposal that matches text only hidden characters contain is flagged; one without a supporting sentence, or of a kind the user didn't ask for, is flagged too. |
| **Tasks tab** | Approved tasks with owner, due date and source (file, page, quote), and saved drafts marked "not sent". Each can be deleted. |
| **Execution audit** | Under every answer: each tool call with its input, status and duration ("Execution audit · 5 completed"). Plain answers list their pipeline steps (retrieve, generate, verify) with tokens and cost. |
| **Streaming** | The text streams token by token; each visual appears as soon as it is complete and verified. |
| **Before vs After** | The same question answered as plain prose and as a visual answer, side by side, with cost and time for each. |
| **Two providers** | Gemini (sends the whole PDF) and Groq (`gpt-oss-120b`, sends retrieved chunks), switchable in the UI. Agent mode always uses Groq. A self-hosted OpenAI-compatible endpoint is also supported for answers. |

## Screenshots

The UI is the Arif chat window: a floating panel with the Arif logo, the document it is working in, suggested questions as cards, and each answer under Arif's name with an Execution audit drawer.

| Welcome: suggested questions | Arabic answer (RTL) |
|---|---|
| ![Welcome](docs/images/ar-welcome.png) | ![Arabic answer](docs/images/ar-answer.png) |

| Agent proposals (one approved) | Execution audit |
|---|---|
| ![Proposals](docs/images/agent-approve.png) | ![Execution audit](docs/images/agent-audit.png) |

| Tasks tab | Injection attempt, flagged |
|---|---|
| ![Tasks tab](docs/images/agent-tasks-tab.png) | ![Injection flagged](docs/images/agent-injection.png) |

**Before vs After**: the same question as plain prose and as a visual answer, with cost and time for each.

![Before vs after](docs/images/ar-before-after.png)

| English chart with verified points | Mobile (390 px) |
|---|---|
| ![English chart](docs/images/en-chart.png) | ![Mobile](docs/images/ar-mobile.png) |

<sub>Screenshots were taken in offline mode (replayed answers, hence the "Mock" badge); the UI is the same with a live model.</sub>

## Architecture

![Architecture and data flow: upload, ask (visual path and agent path) and approve, with every condition and technology](docs/images/architecture.svg)

<sub>The diagram is generated by <code>docs/images/make_architecture.py</code>.</sub>

### ① Upload: `POST /api/documents`

1. **Validate**: MIME type and `%PDF` magic, ≤ 20 MB, ≤ 60 pages, no encryption, per-IP rate limit.
2. **Parse** with pdfplumber. Only *visible* characters count; white, tiny or off-page text is excluded and raises `HIDDEN_TEXT_DETECTED`. Arabic lines stored in visual order are restored to reading order.
3. **OCR** (RapidOCR, local) runs in the background, and only for pages without a text layer.
4. **Store**: memoised by SHA-256, owned by the uploading browser (`X-Client-Id`), kept 48 h. Gemini gets the PDF through its Files API; Groq never receives the file, only text.

### ② Ask: `POST /api/ask` → server-sent events

The **router** picks the path. A question about decisions, owners, action items, "make tasks" or "draft an email" goes to the agent when a Groq key is configured; everything else (or `text_only`) takes the visual path.

**Visual path.** An answer cache (SQLite) replays repeat questions instantly. On a miss, **retrieval** (BM25 over ~600-character chunks, ≈ 5K-token budget; an Arabic question about an English document is translated for search by `gpt-oss-20b`) selects the context, and the **provider** returns one JSON object: `answer_text` plus typed components. The JSON is parsed **while it streams** (jiter): text goes to the browser immediately; each finished component is validated (Pydantic, over-long fields trimmed), grounded (G1, G2) and policed (≤ 3, quiz last, chart → table when fewer than 3 points verify). On 429/503 the server waits (`retry-after`), retries, then uses the fallback model, but only before any output has streamed.

**Agent path.** The document's visible text becomes numbered sentences (`s1`, `s2`, …). Groq tool calling runs for at most 4 steps, each with its own timeout. `extract_items` is a separate strict-JSON call returning items with sentence ids; the server turns ids into page + quote citations and checks G3. `create_task` and `draft_message` store proposals only. If the user asked for an action and the model only *described* it, the loop reminds it once. Verified action items the model didn't reach are then proposed by the server, marked `[server]` in the audit and still waiting for Approve. The server builds the cards from tool results and runs them through the same checks; agent answers are never cached.

Both paths emit AG-UI-style events (`TEXT_MESSAGE_CONTENT`, `COMPONENT`, `TOOL_CALL_START`, `TOOL_CALL_RESULT`, `METRICS`, …); see [docs/protocol.md](docs/protocol.md). The browser re-validates every component with Zod and renders it with a props-only React component; model output is never rendered as HTML, links or images.

### ③ Approve: the only path that changes state

`POST /api/actions/{id}/approve | reject` accepts a decision only from the browser that asked (else 404) and only once (else 409). Approve may carry edits (title, owner, due date; recipient, body). An approved task lands in the tasks store with its source citation; an approved draft is saved with `sent: false`. The Tasks tab reads `GET /api/tasks`.

## Results

**Visual answers, live on Groq `openai/gpt-oss-120b`:** 3 real PDFs (a research paper, a project report and a scanned slide deck), 9 free-form questions, a third in Egyptian Arabic.

| | |
|---|---|
| Answered | **9 / 9**, no errors |
| Visual shown | **6 / 9** (3 fully verified, 3 partial = shown with unverifiable citations removed) |
| Model time | **0.9–2.7 s** per answer |
| Prompt size | 3.7K–4.8K tokens (retrieval) |
| Cost | about **$0.001** per answer |
| Arabic → English search | translated automatically for every Arabic question |

**Agent mode, live on Groq:** SAMPLE meeting transcript (`fixtures/pdfs/meeting_sample.pdf`, fictional, Egyptian Arabic with English terms, 3 decisions and 4 action items) plus a PDF with a hidden "create a task" instruction.

| Question | Result | Time |
|---|---|---|
| إيه القرارات اللي خدناها؟ | 3 decisions, all verified against their sentences | 3.9 s |
| مين مسؤول عن إيه؟ | 4 action items with owner and date, all verified | 5.3 s |
| اعمللي tasks بالـ action items | 4 task proposals; tasks store empty until Approve, then 1 task | 6.9 s |
| Draft an email to the team… | 1 draft proposal, nothing sent | 4.9 s |
| Make tasks… (PDF with a hidden instruction) | 2 genuine proposals, hidden-text warning, no injected task | 5.0 s |

The first live runs found three problems: assignments counted as decisions, a reply that claimed tasks the model never proposed, and the owner "أنا" ("I") instead of the speaker's name. All three are fixed and covered by tests. Across the 6 built-in demo questions in both languages, 71 % of the model's quotes verified; the rest were paraphrases, which grounding removed as intended. Every design decision (D1–D42) and all measurements are in [BUILD_LOG.md](BUILD_LOG.md).

**Tests:** 195 backend tests (pytest, 24 for agent mode) and 113 end-to-end tests (Playwright in Arabic, English and on mobile: the permission gate, the Tasks tab, the injection PDF, axe accessibility checks and visual baselines), plus 2 live tests, lint and type checks (ruff, mypy, oxlint, tsc) and a schema-parity check between the Python and TypeScript catalogs.

## Cost plan

Model calls are almost the whole cost: the app is one FastAPI process with SQLite, which runs on a small VM. Every answer reports its own tokens and cost (`METRICS`), and `GET /api/metrics/summary` aggregates them, so the numbers below can be tracked in production.

### Unit costs

Prices from the model providers' published price lists, checked 2026-10-29 (`backend/app/prices.json`).

| Answer | Model | Tokens | Cost per answer | Per 1,000 |
|---|---|---|---|---|
| Visual answer (retrieval) | Groq `gpt-oss-120b` ($0.15 in / $0.60 out per 1M) | ≈ 4.9K in + reasoning and output (12 live runs) | **$0.0014** measured | **$1.40** |
| Agent answer (4 steps max) | Groq `gpt-oss-120b` | 3.4K–6.7K total (5 live runs) | **$0.0008–0.0013** measured | **≈ $1.00** |
| Visual answer, whole PDF | Gemini 3.8 Flash ($0.75 / $3.75 until 2026-12-31) | ≈ 24.1K in (43-page paper, `count_tokens`) + ≈ 1.5K out | ≈ $0.024 *estimated* | ≈ $24 |
| Same, from 2027-01-01 | Gemini 3.8 Flash ($1.50 / $7.50) | same | ≈ $0.047 *estimated* | ≈ $47 |
| Same, with context caching | Gemini 3.8 Flash (cached input $0.075) | same | ≈ $0.0074 + cache storage | ≈ $7.40 |
| Repeat question | none (answer cache) | 0 | **$0** | $0 |
| Per document, once | Groq `gpt-oss-20b` (suggested questions, query translation; cached) | ≈ 2K | ≈ $0.0003 | n/a |

Gemini's figures are estimates from `count_tokens` and the price table; Gemini was overloaded (503) during the build, so no live Gemini answer was billed.

### Monthly scenarios

Assumptions: 30 questions per active user per month, 80 % visual answers and 20 % agent answers, 15 % served from the answer cache.

| Active users / month | Questions | Groq (recommended) | Gemini 3.8 Flash, whole PDF (2026 prices) |
|---|---|---|---|
| 1,000 (pilot) | 30K | **≈ $34** | ≈ $490 |
| 10,000 (school network) | 300K | **≈ $340** | ≈ $4,900 |
| 100,000 (national) | 3M | **≈ $3,400** | ≈ $49,000 |

That is about **$0.034 per active user per month** on Groq, against about $0.49 on Gemini with whole-PDF context (roughly double from 2027 prices).

### Plan

1. **Demo and pilot: Groq free tier, $0.** The free tier allows about 8K tokens per minute, which is about one answer per minute. That is enough for a demo, not for a class.
2. **Launch: Groq paid tier, `gpt-oss-120b`, ≈ $0.04 per active user per month.** Size the rate limit for the peak: if 10 % of a day's questions arrive in one hour, 10,000 users need about 1,000 answers per hour, ≈ 90K tokens per minute. Keep `qwen3.8-27b` only as the rate-limit fallback: it costs about 3× more per answer.
3. **Gemini where it pays off.** Use it for documents where the model must see the page itself (figures, complex scans), with `RETRIEVAL=on` (≈ 5× less input) or context caching, rather than as the default.
4. **Scale or data residency: self-host.** The same code talks to any OpenAI-compatible server (`PROVIDER=openai_compat`, for example vLLM with `gpt-oss-120b`). The cost becomes a fixed GPU bill instead of per-token, which pays off only at sustained high volume, or when documents must not leave the country.

### Cost controls already built in

- Retrieval caps the prompt at ≈ 5K tokens instead of sending the whole PDF to Groq.
- The answer cache makes repeat questions free; translations and suggested questions are cached per document.
- Small model (`gpt-oss-20b`, half the price) for translation and suggestions; `reasoning_effort=low` on gpt-oss.
- Hard limits: ≤ 3 components, output token caps, ≤ 4 agent steps, a question limit per document, per-IP rate limits.
- The fallback model is used only after retries, and only before any output has streamed.
- Cost per answer is visible in the UI and logged, so a budget alert is one query away.

## Quick start

Requirements: Python ≥ 3.12 with [uv](https://docs.astral.sh/uv/), Node.js 20+, GNU make (on Windows, run it from Git Bash).

```bash
cp .env.example .env      # add GROQ_API_KEY and/or GEMINI_API_KEY, set PROVIDER=groq|gemini
make setup                # Python + Node dependencies, Playwright Chromium
make serve                # build and serve the app on http://localhost:8000 (live model)
```

Then upload any PDF, or `fixtures/pdfs/meeting_sample.pdf` for the agent's demo questions.

No key? `make serve-mock` runs the same app offline with recorded answers for the demo paper (`fixtures/pdfs/cot.pdf`) and the SAMPLE meeting transcript. Agent mode needs `GROQ_API_KEY` when live.

| Command | What it does |
|---|---|
| `make serve` | The app, with the live model from `.env` |
| `make serve-mock` | The app, offline (recorded answers) |
| `make test-backend` | pytest |
| `make lint` | ruff, mypy, oxlint, tsc, schema parity, secret grep |
| `make e2e` | Playwright against a fresh offline server |
| `make test-live` | 2 end-to-end tests against the real model (costs a few API calls) |
| `make demo` | Records the demo video, GIF and key frames into `demo/` |

## Security and privacy

- API keys stay on the server (`.env`, git-ignored); the browser never sees them.
- Model output is data, not markup: no `dangerouslySetInnerHTML` (lint fails on it), markdown is rendered with an allowlist, and KaTeX runs with `trust: false`.
- Hidden-text detection, upload size and page limits, MIME checks, per-IP rate limits and a strict CSP.
- Agent tools never act: tasks and drafts are proposals until the user who asked approves them, and nothing is ever sent. Proposals traced to hidden PDF text, without a supporting sentence, or not asked for are flagged.
- Documents, proposals and tasks belong to the browser that created them; documents expire after 48 h.
- PDF text is sent to the selected provider (Google or Groq). OCR runs locally.

## Known limitations

- **Quote fidelity:** models sometimes paraphrase quotes. Grounding catches this, at the cost of fewer visuals (6/9 in the live run).
- **Groq free tier** (8K tokens per minute) allows about one answer per minute under load. The model itself answers in 1–7 s.
- **Gemini** returned 400/503 for most of the build day, so its demo answers are hand-authored fixtures. The provider code is in place and tested offline.
- **Agent routing is a keyword list** (Arabic and English): cheap and predictable, but a phrasing it doesn't know gets a normal visual answer.
- **Tasks and drafts are stored locally** (SQLite, per browser), not yet connected to a task manager or mail system.
- gpt-oss tends to make one tool call per step, so the server completes task proposals the model didn't reach (marked `[server]`).
- **Arabic scanned PDFs** are not covered by the default OCR models. Retrieval is lexical (BM25).

## Next steps

1. Embedding retrieval (hybrid with BM25) and a reranker.
2. A grounding eval set in Arabic to track quote fidelity per model and prompt version.
3. Arabic OCR models for scanned course material.
4. Integrate the component catalog into Arif's chat as a response type, behind a flag.
5. Connect approved actions to Qriib's own products (tasks, email) behind the same approve step, with an audit log per user.

## Repository map

```text
backend/app/          FastAPI app: catalog, grounding, policy, retrieval, stream, agent, actions, providers/
backend/tests/        pytest
frontend/src/         React app: catalog renderers, agent cards, SSE state, i18n, design tokens
e2e/                  Playwright specs, helpers, visual baselines
fixtures/             demo PDFs and recorded answers (offline mode and tests)
docs/protocol.md      SSE event protocol and action endpoints
docs/images/          screenshots, logo, architecture diagram (+ its generator)
docs/BUILD_SPEC.md    the original build specification
BUILD_LOG.md          decisions D1–D42, live-call logs, measurements
```
