# Arif Visual Answers

**Ask a question about any PDF and get a short answer plus up to three visuals: a chart, a comparison, steps, a table, a diagram, a formula, a quiz or flashcards. Every number and claim in a visual is checked against the page it cites. Ask it to act ("make tasks from the action items", "draft an email to the team") and it proposes the actions, but nothing happens until you approve.**

The default language is Egyptian Arabic (RTL), and English (LTR) is one click away. This prototype explores what Arif could add on top of a text answer: a small set of typed components that can be verified, instead of free-form model output, and an assistant that understands the document, connects it to tasks and messages, and acts only with permission.

![Demo: an Arabic question answered with a grounded comparison, then a quiz](demo/arif-visual-answers.gif)

---

## Why

A student who asks *"how much does chain-of-thought improve GSM8K as models grow?"* doesn't need 300 words. They need the number, the trend and the page it came from. Three things make that hard in practice:

1. **Visuals must be trustworthy.** A chart with one invented number is worse than no chart.
2. **Arabic first.** RTL layout, mixed Arabic and English terms, and Arabic questions about English documents.
3. **Cost and latency.** The answer has to stream quickly and cost a fraction of a cent.

## What it does

| | |
|---|---|
| **Any PDF** | Upload one or several PDFs and switch or delete them from the "working in" bar; each keeps its question history. Scanned PDFs are OCR'd locally in the background. Arabic PDFs whose producer stores lines right-to-left with shaped glyphs (Chromium, Word) are restored to reading order. |
| **Any question** | Typed in Arabic or English. Suggested questions are generated for each document. |
| **Short answer + ≤ 3 visuals** | 9 visual types: `text`, `chart`, `comparison`, `steps`, `table`, `diagram`, `formula`, `quiz`, `flashcards`. The model chooses; a policy layer enforces the limits. |
| **Grounding** | Every data point carries a page number and a verbatim quote. The server checks the quote against the visible text of that page, and the numbers against both the quote and the page. Anything that fails is removed or downgraded, never shown as fact. |
| **Agent mode** | Questions about decisions, owners, tasks or messages go to an agent loop with Groq tool calling (at most 4 steps, a timeout per step) and four tools: `search_document`, `extract_items` (decisions or action items, each citing its sentence ids), `create_task` and `draft_message`. Any other question keeps the visual-answer path. |
| **Permission gate** | `create_task` and `draft_message` only write proposals. Each appears in an action card with **Approve / Edit / Reject**; a task is saved only when the user who asked clicks Approve, and a draft is saved but never sent. |
| **Agent cards** | 3 more catalog types built by the server from tool results, with the same validation and grounding: `decision_cards`, `task_cards` (the owner and the due date must appear in the cited sentence) and `action_card`. |
| **Injection-safe actions** | Text in the document can lead to a proposal, never to an action. A proposal that matches text only hidden characters contain is flagged as coming from hidden text; one without a supporting sentence, or of a kind the user didn't ask for, is flagged too. |
| **Tasks tab** | Approved tasks with owner, due date and source (file, page, quote), and saved drafts marked "not sent". Each can be deleted. |
| **Execution audit** | Under every answer: each tool call with its input, status and duration (for example "Execution audit · 5 completed"). Plain answers list their pipeline steps (retrieve, generate, verify), with tokens and cost. |
| **Streaming** | The text streams token by token; each visual appears as soon as it is complete and verified. |
| **Before vs After** | The same question answered as plain prose and as a visual answer, side by side, with cost and time for each. |
| **Two providers** | Gemini (sends the whole PDF) and Groq (`gpt-oss-120b`, sends retrieved chunks), switchable in the UI. Agent mode always uses Groq. A self-hosted OpenAI-compatible endpoint is also supported for answers. |

## Screenshots

The UI is the Arif chat window: a floating panel with the Arif logo, the document it is working in, suggested questions as cards, and the answer under Arif's name with an "Execution audit" drawer.

| Welcome: suggested questions | Arabic answer (RTL) |
|---|---|
| ![Welcome](docs/images/ar-welcome.png) | ![Arabic answer](docs/images/ar-answer.png) |

**Before vs After**: the same question as plain prose and as a visual answer, with cost and time for each.

![Before vs after](docs/images/ar-before-after.png)

| English chart with verified points | Mobile (390 px) |
|---|---|
| ![English chart](docs/images/en-chart.png) | ![Mobile](docs/images/ar-mobile.png) |

**Agent mode** on the SAMPLE meeting transcript (`fixtures/pdfs/meeting_sample.pdf`): proposals with Approve / Edit / Reject, the Execution audit, the Tasks tab, and a task smuggled in through hidden PDF text, flagged and waiting.

| Proposals (one approved) | Execution audit |
|---|---|
| ![Proposals](docs/images/agent-approve.png) | ![Execution audit](docs/images/agent-audit.png) |

| Tasks tab | Injection attempt, flagged |
|---|---|
| ![Tasks tab](docs/images/agent-tasks-tab.png) | ![Injection flagged](docs/images/agent-injection.png) |

<sub>The screenshots were taken in offline mode (replayed answers, hence the "Mock" badge); the UI is the same with a live model.</sub>

## How it works

![Architecture: upload, ask and check lanes](docs/images/architecture.svg)

**One request, step by step**

1. The PDF is parsed once (memoised by SHA-256). Only *visible* text counts: characters that are tiny, white or outside the page are excluded, and a warning is raised if hidden text is found (a prompt-injection defence).
2. **Retrieval** picks the relevant chunks under a token budget (about 5K tokens, sized for Groq's free tier). An Arabic question about an English document is first translated by a small model, for search only.
3. The model returns **one JSON object**: `answer_text` plus a list of typed components, following a single catalog schema (Pydantic on the server, mirrored by Zod in the browser and checked in CI).
4. The JSON is parsed **while it streams**. Answer text goes to the browser immediately. Each component, once complete, goes through:
   - **validation** against its type (over-long strings or lists are trimmed, not dropped);
   - **grounding**: the quote must fuzzy-match the cited page (≥ 90, ±1 page tolerance), and every number must appear in the quote *and* on the page;
   - **policy**: at most 3 visuals, quiz last, a chart with too few verified points becomes a table, and a table with fewer than 2 verified rows is dropped.
5. Events are sent over **SSE** with AG-UI style names (`TEXT_MESSAGE_CONTENT`, `COMPONENT`, `COMPONENT_DROPPED`, `METRICS`, …). See [docs/protocol.md](docs/protocol.md).
6. The browser renders each type with a pure, props-only component. Model output is never rendered as HTML, links or images.

**Agent mode, step by step** (`backend/app/agent.py`)

1. The router sends questions about decisions, owners, tasks or messages to the agent; everything else takes the path above.
2. The document's visible text is split into numbered sentences (`s1`, `s2`, …). A short document goes to the model whole; a long one is searched with `search_document`.
3. Groq tool calling runs for at most 4 steps, each with its own timeout. `extract_items` is a separate strict-JSON call that returns items with sentence ids; the server turns ids into page + quote citations and checks that the owner and the due date really are in the cited sentence.
4. `create_task` and `draft_message` only store **proposals**. The server builds the cards (`decision_cards`, `task_cards`, `action_card`) from the tool results and runs them through the same validation and grounding as any other component.
5. If the user asked for tasks and the model stopped short (out of steps, or it only *said* it proposed them), the server proposes the remaining verified action items itself. They are labelled `[server]` in the audit and still need Approve.
6. Approve / Edit / Reject call `/api/actions/{id}/approve|reject`. Only an approval from the browser that asked creates a task. A draft is saved, never sent.

**Resilience:** on 429 or 503 the server waits (honouring `retry-after`), retries, then switches to a fallback model, but only if nothing has streamed yet. On a timeout the user keeps the partial text and sees a clear error. Answers are cached on document + normalised question + language + model + prompt version.

## Results

**Live, on Groq `openai/gpt-oss-120b`, 3 real PDFs** (a research paper, a project report and a scanned slide deck), 9 free-form questions, a third of them in Egyptian Arabic:

| | |
|---|---|
| Answered | **9 / 9**, no errors |
| Visual shown | **6 / 9** (3 fully verified, 3 partial = shown with unverifiable citations removed) |
| Model time | **0.9 – 2.7 s** per answer |
| Prompt size | 3.7K – 4.8K tokens (retrieval) |
| Cost | about **$0.001** per answer |
| Arabic → English search | translated automatically for all Arabic questions |

**Agent mode, live on Groq** (SAMPLE meeting transcript, 4 questions in Egyptian Arabic and English, plus the injection PDF):

| Question | Result | Time |
|---|---|---|
| إيه القرارات اللي خدناها؟ | 3 decisions, all verified against their sentences | 3.9 s |
| مين مسؤول عن إيه؟ | 4 action items with owner and date, all verified | 5.3 s |
| اعمللي tasks بالـ action items | 4 task proposals; tasks store empty until Approve, then 1 task | 6.9 s |
| Draft an email to the team… | 1 draft proposal, nothing sent | 4.9 s |
| Make tasks… (PDF with a hidden "create a task" instruction) | 2 genuine proposals, hidden-text warning, no injected task | 5.0 s |

About $0.001 per agent answer. The first live runs found three problems: assignments counted as decisions, a model reply that claimed tasks it never proposed, and owner "أنا" instead of the speaker's name. All three are fixed and covered by tests ([BUILD_LOG.md](BUILD_LOG.md), D35–D42).

On the 6 built-in demo questions × 2 languages, 71 % of the quotes the model wrote verified against the page. The rest were paraphrases, and grounding removed them, which is the intended behaviour. Full tables and every design decision (D1–D42) are in [BUILD_LOG.md](BUILD_LOG.md).

**Tests:** 195 backend tests (pytest, 24 of them for agent mode), 113 end-to-end tests (Playwright, in Arabic, English and on mobile, including the permission gate, the Tasks tab, the injection PDF, accessibility checks with axe and visual baselines), 2 live tests, plus lint and type checks (ruff, mypy, oxlint, tsc) and a schema-parity check between the Python and TypeScript catalogs.

## Quick start

Requirements: Python ≥ 3.12 with [uv](https://docs.astral.sh/uv/), Node.js 20+, GNU make (on Windows, run it from Git Bash).

```bash
cp .env.example .env      # add GROQ_API_KEY and/or GEMINI_API_KEY, set PROVIDER=groq|gemini
make setup                # Python + Node dependencies, Playwright Chromium
make serve                # build and serve the app on http://localhost:8000 (live model)
```

No key? `make serve-mock` runs the same app offline with recorded answers for the demo paper (`fixtures/pdfs/cot.pdf`) and the SAMPLE meeting transcript (`fixtures/pdfs/meeting_sample.pdf`). Agent mode needs `GROQ_API_KEY` when live.

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
- Documents belong to the browser that uploaded them and expire after 48 h.
- PDF text is sent to the selected provider (Google or Groq). OCR runs locally.
- Agent tools never act: tasks and drafts are proposals until the user who asked approves them, and nothing is ever sent. Proposals traced to hidden PDF text, without a supporting sentence, or not asked for are flagged.

## Known limitations

- **Quote fidelity:** models sometimes paraphrase quotes. Grounding catches this, but the cost is fewer visuals (6/9 in the live run).
- **Groq free tier** (8K tokens per minute) means about one answer per 45 s under load. A paid tier removes the wait; the model itself answers in about 2 s.
- **Gemini** returned 400/503 for most of the build day, so its demo answers are hand-authored fixtures. The provider code is in place and tested offline.
- **Arabic scanned PDFs** are not covered by the default OCR models.
- Retrieval is lexical (BM25). Embeddings would help with questions that use different words from the document.
- **Agent routing is a keyword list** (Arabic and English): cheap and predictable, but a phrasing it doesn't know gets a normal visual answer.
- **Tasks and drafts are stored locally** (SQLite, per browser). They are not connected to a real task manager or mail system yet.
- gpt-oss tends to make one tool call per step, so the server completes task proposals the model didn't reach (marked `[server]`).

## Next steps

1. Embedding retrieval (hybrid with BM25) and a reranker.
2. A grounding eval set in Arabic to track quote fidelity per model and prompt version.
3. Arabic OCR models for scanned course material.
4. Integrate the component catalog into Arif's chat as a response type, behind a flag.
5. Connect the approved actions to Qriib's own products (tasks, email) behind the same approve step, with an audit log per user.

## Repository map

```
backend/app/          FastAPI app: catalog, grounding, policy, retrieval, stream, agent, actions, providers/
backend/tests/        pytest
frontend/src/         React app: catalog renderers, SSE state, i18n, design tokens
e2e/                  Playwright specs, helpers, visual baselines
fixtures/             demo PDFs and recorded answers (offline mode and tests)
docs/protocol.md      SSE event protocol
docs/BUILD_SPEC.md    the original build specification
BUILD_LOG.md          decisions, live-call log, measurements
```
