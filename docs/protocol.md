# Arif Visual Answers — streaming protocol

`POST /api/ask` and `POST /api/ask_text` return `text/event-stream`. Each message is

```
event: <TYPE>
data: <json>

```

The client reads it with `fetch` + `ReadableStream` (not `EventSource`, which only does GET). Request body:
`{doc_id, question (1–500 chars), lang: "ar"|"en", text_only?: bool}`.

## Events

Event names follow AG-UI 1.0 so a real AG-UI adapter is a rename, not a redesign.

| Event | Data | AG-UI mapping |
|---|---|---|
| `RUN_STARTED` | `{run_id, doc_id, lang, model, provider, cached: bool, agent?: true}` | `RUN_STARTED` |
| `TOOL_CALL_START` | agent mode: `{tool_call_id, tool_call_name, step, input}` (`input` is a short summary of the arguments) | `TOOL_CALL_START` |
| `TOOL_CALL_RESULT` | agent mode: `{tool_call_id, tool_call_name, step, input, status: "ok"\|"proposed"\|"error", duration_ms, summary}` | `TOOL_CALL_RESULT` |
| `TEXT_MESSAGE_START` | `{message_id}` | same |
| `TEXT_MESSAGE_CONTENT` | `{message_id, delta}` | same |
| `TEXT_MESSAGE_END` | `{message_id}` | same |
| `COMPONENT_PLANNED` | `{component_id, type}` — show a skeleton | `TOOL_CALL_START` (tool name = component type) |
| `COMPONENT` | `{component_id, type, props, verification: {status: "verified"\|"partial"\|"unverified", dropped_points: n}, downgraded_from?}` | `TOOL_CALL_ARGS` + `TOOL_CALL_END`; A2UI: one catalog component in a surface update |
| `COMPONENT_DROPPED` | `{component_id, type, reason, fallback_text?}` | custom |
| `WARNING` | `{code, message, pages?}` — `HIDDEN_TEXT_DETECTED`, `FALLBACK_MODEL_USED`, `TRUNCATED_OUTPUT`, `RATE_LIMIT_WAIT`, `OCR_USED`, `AGENT_STEP_LIMIT`, `AGENT_UNAVAILABLE` | custom |
| `METRICS` | tokens, cost, latency, component counts, cache (see docs/BUILD_SPEC.md §9); agent mode adds `mode: "agent"` and `tools: [...]` (the audit) | `STATE_SNAPSHOT` |
| `RUN_ERROR` | `{code, message}` — terminal | `RUN_ERROR` |
| `RUN_FINISHED` | `{run_id}` — terminal | `RUN_FINISHED` |

### Ordering guarantees

- `RUN_STARTED` is first. Exactly one of `RUN_FINISHED` or `RUN_ERROR` is last.
- All `TEXT_MESSAGE_CONTENT` deltas arrive before `TEXT_MESSAGE_END`. Concatenating them gives the final `answer_text`.
- `COMPONENT_PLANNED` for a component arrives before its `COMPONENT` or `COMPONENT_DROPPED`. Every planned component ends in exactly one of the two.
- At most 3 `COMPONENT` events. A `quiz` is always the last `COMPONENT`.
- `component_id` is positional (`c1`, `c2`, …), so a skeleton and its component always share an id. `props.id` is whatever id the model produced.
- `METRICS` comes just before the terminal event. On a timeout it comes before `RUN_ERROR`, after any text that arrived.
- An app-cache hit replays the stored events immediately with `RUN_STARTED.cached = true` and `METRICS.cache.app_cache_hit = true`.

### Drop reasons

`needs_visual_false`, `unknown_type`, `invalid` (failed schema validation), `empty_reason`, `duplicate_id`, `mismatched_attribute_keys`, `insufficient_verified_points` (chart), `insufficient_verified_rows` (table), `no_verified_questions` (quiz), `only_one_quiz`, `too_many_components`, `incomplete` (the output was cut off mid-component), `no_verified_items` (agent cards with no grounded item).

A chart with fewer than 3 verified points but at least 2 arrives as `COMPONENT` with `type: "table"` and `downgraded_from: "chart"`.

## Agent mode

A question that asks for decisions, owners, tasks or a message (`agent.wants_agent`) runs `AgentRun` instead of the visual answer: Groq tool calling, at most 4 model calls, each with its own timeout (`AGENT_STEP_TIMEOUT_S`). Order: `RUN_STARTED {agent: true}`, any `WARNING`, `TOOL_CALL_START`/`TOOL_CALL_RESULT` pairs, then the reply text, then up to three components built by the server from tool results (`decision_cards`, `task_cards`, `action_card`), `METRICS`, `RUN_FINISHED`. Agent answers are never cached.

`action_card` lists proposals. Nothing happens until the user who asked decides:

| Endpoint | Effect |
|---|---|
| `POST /api/actions/{proposal_id}/approve` | body `{title?, owner?, due_date?, to?, body?}` (edits). A `create_task` proposal becomes a task; a `draft_message` is saved as a draft (`sent: false`, never sent). 404 for another browser's proposal, 409 if already decided. |
| `POST /api/actions/{proposal_id}/reject` | marks it rejected; nothing is created. |
| `GET /api/tasks` | `{tasks, drafts}` for this browser (`X-Client-Id`). |
| `DELETE /api/tasks/{id}` | deletes one task or draft. |

Proposal flags: `FROM_HIDDEN_TEXT` (the proposal matches text that only hidden characters contain), `UNVERIFIED_SOURCE` (no cited sentence supports it), `NOT_REQUESTED` (the user's question didn't ask for this kind of action).

## Component props

The props are the Pydantic models in `backend/app/catalog.py`. Their JSON Schema is exported to `frontend/src/catalog/schema.json`, which the Zod schemas in `frontend/src/catalog/schemas.ts` are tested against. `frontend/src/catalog/gemini.schema.json` is the exact schema sent to the model (`SCHEMA_MODE=flat`).

## Future adapters

**AG-UI.** A `/api/agui` endpoint would wrap the same generator. Text events pass through unchanged. `COMPONENT_PLANNED` becomes `TOOL_CALL_START {toolCallId: component_id, toolCallName: type}`. `COMPONENT` becomes `TOOL_CALL_ARGS {delta: JSON.stringify(props)}` followed by `TOOL_CALL_END`. `COMPONENT_DROPPED` becomes `TOOL_CALL_END` plus a `CUSTOM` event. `METRICS` becomes `STATE_SNAPSHOT`. A CopilotKit frontend would then register each catalog component as a render-only tool with the same React components.

**A2UI.** The catalog is already flat and keyed by component id, which is A2UI's model. Each `COMPONENT` maps to one `surfaceUpdate` entry `{id: component_id, component: {<type>: props}}` in a custom catalog that declares the nine types. Verification status and citations would travel as extra props, because A2UI has no native notion of grounding. RTL would have to come from our renderer, since A2UI v0.9 does not specify text direction.
